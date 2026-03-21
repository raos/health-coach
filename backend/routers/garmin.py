import json
import os
from datetime import date, timedelta, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.engine import get_db
from database.models import GarminDailyCache
from services.garmin_service import garmin_service

router = APIRouter(prefix="/api/garmin", tags=["garmin"])


# ── Cache helpers ──────────────────────────────────────────────────────────────

def _upsert_cache(db: Session, **kwargs) -> None:
    """Insert or update a GarminDailyCache row keyed by date."""
    row_date = kwargs.pop("date")
    existing = db.query(GarminDailyCache).filter(GarminDailyCache.date == row_date).first()
    if existing:
        for k, v in kwargs.items():
            if v is not None:
                setattr(existing, k, v)
        existing.synced_at = datetime.utcnow()
    else:
        db.add(GarminDailyCache(date=row_date, synced_at=datetime.utcnow(), **kwargs))


def _date_range(days: int) -> list:
    today = date.today()
    return [today - timedelta(days=i) for i in range(days, 0, -1)]


def _require_auth():
    if not garmin_service.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Garmin not configured. Add GARMIN_EMAIL and GARMIN_PASSWORD to .env"
        )
    if not garmin_service.is_authenticated():
        raise HTTPException(
            status_code=503,
            detail="Garmin not authenticated. Go to Settings → Garmin Connect → Connect."
        )


@router.get("/status")
def garmin_status():
    if not garmin_service.is_configured():
        return {"configured": False, "authenticated": False}
    # Actually test the connection — login(tokenstore=) refreshes the OAuth2
    # token if needed, or raises if the refresh token is also expired.
    # If _client is already cached in memory this is near-instant.
    try:
        garmin_service._get_client()
        authenticated = True
    except Exception:
        authenticated = False
    return {"configured": True, "authenticated": authenticated}


class TokenImportRequest(BaseModel):
    oauth1: dict
    oauth2: dict


@router.post("/import-tokens")
def import_tokens(payload: TokenImportRequest):
    """Upload pre-authenticated Garmin session tokens from a local machine."""
    token_dir = garmin_service._token_dir()
    os.makedirs(token_dir, exist_ok=True)
    with open(os.path.join(token_dir, "oauth1_token.json"), "w") as f:
        json.dump(payload.oauth1, f)
    with open(os.path.join(token_dir, "oauth2_token.json"), "w") as f:
        json.dump(payload.oauth2, f)
    # Reset client so it picks up the new tokens on next data request
    garmin_service._client = None
    return {"status": "ok", "token_dir": token_dir}


@router.post("/login")
def garmin_login():
    """Initiate Garmin login. Returns status 'ok' or 'mfa_required'."""
    if not garmin_service.is_configured():
        raise HTTPException(status_code=400, detail="GARMIN_EMAIL and GARMIN_PASSWORD not set in .env")
    try:
        status = garmin_service.start_login()
        return {"status": status}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


class MfaRequest(BaseModel):
    otp: str


@router.post("/verify-mfa")
def verify_mfa(payload: MfaRequest):
    """Submit the OTP from Garmin's MFA email to complete login."""
    try:
        garmin_service.submit_mfa(payload.otp)
        return {"status": "ok"}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sleep")
def get_sleep(for_date: Optional[date] = None):
    _require_auth()
    try:
        return garmin_service.get_sleep_data(for_date)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/body-battery")
def get_body_battery(for_date: Optional[date] = None):
    _require_auth()
    try:
        return garmin_service.get_body_battery(for_date)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/steps")
def get_steps(for_date: Optional[date] = None):
    _require_auth()
    try:
        return garmin_service.get_steps(for_date)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/vo2max")
def get_vo2max():
    _require_auth()
    try:
        return {"vo2max": garmin_service.get_vo2max()}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/sleep/range")
def get_sleep_range(days: int = 30, db: Session = Depends(get_db)):
    _require_auth()
    # Try live fetch; cache any results that come back
    try:
        live = garmin_service.get_sleep_range(days)
        for row in live:
            _upsert_cache(
                db,
                date=date.fromisoformat(row["date"]),
                sleep_duration_hours=row.get("duration_hours"),
                sleep_score=row.get("score"),
                deep_min=row.get("deep_min"),
                rem_min=row.get("rem_min"),
                light_min=row.get("light_min"),
            )
        db.commit()
    except Exception:
        pass  # Fall through to cache

    # Serve from cache (covers gaps when live data is unavailable)
    start = date.today() - timedelta(days=days)
    rows = (
        db.query(GarminDailyCache)
        .filter(GarminDailyCache.date > start, GarminDailyCache.sleep_duration_hours.isnot(None))
        .order_by(GarminDailyCache.date)
        .all()
    )
    return [
        {
            "date": r.date.isoformat(),
            "duration_hours": r.sleep_duration_hours,
            "score": r.sleep_score,
            "deep_min": r.deep_min,
            "rem_min": r.rem_min,
            "light_min": r.light_min,
        }
        for r in rows
    ]


@router.get("/steps/range")
def get_steps_range(days: int = 30, db: Session = Depends(get_db)):
    _require_auth()
    try:
        live = garmin_service.get_steps_range(days)
        for row in live:
            _upsert_cache(db, date=date.fromisoformat(row["date"]), steps=row.get("steps"))
        db.commit()
    except Exception:
        pass

    start = date.today() - timedelta(days=days)
    rows = (
        db.query(GarminDailyCache)
        .filter(GarminDailyCache.date > start, GarminDailyCache.steps.isnot(None))
        .order_by(GarminDailyCache.date)
        .all()
    )
    return [{"date": r.date.isoformat(), "steps": r.steps} for r in rows]


@router.get("/resting-hr/range")
def get_resting_hr_range(days: int = 30, db: Session = Depends(get_db)):
    _require_auth()
    try:
        live = garmin_service.get_resting_hr_range(days)
        for row in live:
            _upsert_cache(db, date=date.fromisoformat(row["date"]), resting_hr=row.get("rhr"))
        db.commit()
    except Exception:
        pass

    start = date.today() - timedelta(days=days)
    rows = (
        db.query(GarminDailyCache)
        .filter(GarminDailyCache.date > start, GarminDailyCache.resting_hr.isnot(None))
        .order_by(GarminDailyCache.date)
        .all()
    )
    return [{"date": r.date.isoformat(), "rhr": r.resting_hr} for r in rows]


@router.get("/debug/tokens")
def debug_tokens():
    """Check what token files exist and whether they contain valid JSON."""
    token_dir = garmin_service._token_dir()
    result = {"token_dir": token_dir, "files": {}}
    for fname in ["oauth1_token.json", "oauth2_token.json"]:
        fpath = os.path.join(token_dir, fname)
        if not os.path.exists(fpath):
            result["files"][fname] = {"exists": False}
            continue
        try:
            with open(fpath) as f:
                content = f.read()
            parsed = json.loads(content)
            result["files"][fname] = {"exists": True, "size": len(content), "keys": list(parsed.keys())}
        except Exception as e:
            result["files"][fname] = {"exists": True, "error": str(e)}
    return result


@router.get("/debug/raw")
def debug_raw():
    """Return raw API responses for HRV and resting HR to inspect field names."""
    _require_auth()
    from datetime import date, timedelta
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    client = garmin_service._get_client()
    return {
        "hrv_raw": client.get_hrv_data(yesterday),
        "rhr_raw": client.get_rhr_day(yesterday),
    }


@router.get("/snapshot")
def get_snapshot():
    """All health metrics in one call — used by the Health Advisor."""
    _require_auth()
    try:
        return garmin_service.get_health_snapshot()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
