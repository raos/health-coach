import json
import os
from datetime import date, timedelta, datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database.engine import get_db
from database.models import GarminDailyCache, Vo2MaxLog
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
        return {"configured": False, "authenticated": False, "has_saved_tokens": False}
    # check_connection() is cached — won't hammer Garmin on every page load.
    # If _client is already in memory it returns instantly.
    authenticated = garmin_service.check_connection()
    return {
        "configured": True,
        "authenticated": authenticated,
        "has_saved_tokens": garmin_service.has_saved_tokens(),
    }


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
    # Reset client and cache so next check re-tests with the new tokens
    garmin_service._client = None
    garmin_service.invalidate_status_cache()
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
        msg = str(e)
        if "429" in msg or "too many" in msg.lower() or "Max retries" in msg:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Garmin is rate-limiting this server's IP address (429 Too Many Requests). "
                    "This happens when too many login attempts come from the same IP. "
                    "Please wait 24–48 hours, then try again — or use the Token Import option "
                    "below to upload tokens from your local machine."
                ),
            )
        raise HTTPException(status_code=400, detail=msg)


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
def get_vo2max(db: Session = Depends(get_db)):
    _require_auth()
    try:
        value = garmin_service.get_vo2max()
        if value is not None:
            today = date.today()
            existing = db.query(Vo2MaxLog).filter(Vo2MaxLog.date == today).first()
            if existing:
                existing.vo2max = value
            else:
                db.add(Vo2MaxLog(date=today, vo2max=value, source="garmin"))
            db.commit()
        return {"vo2max": value}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/vo2max/sync")
def sync_vo2max_history(days: int = 90, db: Session = Depends(get_db)):
    """Try to backfill VO2 max history from Garmin for the past N days."""
    _require_auth()
    saved = 0
    for i in range(days, -1, -1):
        d = date.today() - timedelta(days=i)
        try:
            data = garmin_service._get_client().get_max_metrics(d.isoformat())
            if data and isinstance(data, list) and len(data) > 0:
                value = data[0].get("generic", {}).get("vo2MaxPreciseValue")
                if value is not None:
                    existing = db.query(Vo2MaxLog).filter(Vo2MaxLog.date == d).first()
                    if existing:
                        existing.vo2max = value
                    else:
                        db.add(Vo2MaxLog(date=d, vo2max=value, source="garmin"))
                    saved += 1
        except Exception:
            continue
    db.commit()
    return {"synced": saved}


@router.get("/sleep/range")
def get_sleep_range(days: int = 30, db: Session = Depends(get_db)):
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


# ── Paste-data endpoint (JWT auth, called from Settings UI) ───────────────────

class PasteDataRequest(BaseModel):
    json_data: str  # raw JSON string copied from Garmin Connect DevTools


@router.post("/paste-data")
def paste_data_from_ui(payload: PasteDataRequest, db: Session = Depends(get_db)):
    """
    Parse a raw Garmin daily summary JSON (copied from DevTools) and upsert
    into GarminDailyCache. Accepts the usersummary format:
    {"calendarDate": "...", "totalSteps": ..., "restingHeartRate": ..., ...}
    """
    try:
        data = json.loads(payload.json_data)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object, not an array.")

    date_str = data.get("calendarDate") or data.get("summaryDate")
    if not date_str:
        raise HTTPException(status_code=400, detail="No 'calendarDate' field found in JSON.")

    try:
        row_date = date.fromisoformat(date_str[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date_str}")

    steps = data.get("totalSteps") or data.get("steps")
    resting_hr = data.get("restingHeartRate") or data.get("restingHeartRateValue")

    if steps is None and resting_hr is None:
        raise HTTPException(status_code=400, detail="No usable fields found (totalSteps, restingHeartRate).")

    existing = db.query(GarminDailyCache).filter(GarminDailyCache.date == row_date).first()
    if existing:
        if steps is not None:
            existing.steps = int(steps)
        if resting_hr is not None:
            existing.resting_hr = int(resting_hr)
        existing.synced_at = datetime.utcnow()
    else:
        db.add(GarminDailyCache(
            date=row_date,
            steps=int(steps) if steps is not None else None,
            resting_hr=int(resting_hr) if resting_hr is not None else None,
            synced_at=datetime.utcnow(),
        ))
    db.commit()

    return {
        "date": row_date.isoformat(),
        "steps": int(steps) if steps is not None else None,
        "resting_hr": int(resting_hr) if resting_hr is not None else None,
    }


# ── Push-data endpoint (MCP API key auth, no Garmin login required) ────────────

class DailyRecord(BaseModel):
    date: date
    sleep_duration_hours: Optional[float] = None
    sleep_score: Optional[int] = None
    deep_min: Optional[int] = None
    rem_min: Optional[int] = None
    light_min: Optional[int] = None
    steps: Optional[int] = None
    resting_hr: Optional[int] = None


class Vo2Record(BaseModel):
    date: date
    vo2max: float


class PushDataPayload(BaseModel):
    daily: List[DailyRecord] = []
    vo2max: List[Vo2Record] = []


@router.post("/push-data")
def push_data(
    payload: PushDataPayload,
    key: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Accept Garmin data from an external script and write it to the local cache.
    Authenticated with the MCP API key (?key=<MCP_API_KEY>) — no Garmin login needed.
    This lets a local script push data to the deployed Railway app without the
    backend ever needing to authenticate directly to Garmin.
    """
    if not settings.mcp_api_key or key != settings.mcp_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    upserted_daily = 0
    for record in payload.daily:
        existing = db.query(GarminDailyCache).filter(GarminDailyCache.date == record.date).first()
        if existing:
            for field in ("sleep_duration_hours", "sleep_score", "deep_min", "rem_min",
                          "light_min", "steps", "resting_hr"):
                val = getattr(record, field)
                if val is not None:
                    setattr(existing, field, val)
            existing.synced_at = datetime.utcnow()
        else:
            db.add(GarminDailyCache(
                date=record.date,
                sleep_duration_hours=record.sleep_duration_hours,
                sleep_score=record.sleep_score,
                deep_min=record.deep_min,
                rem_min=record.rem_min,
                light_min=record.light_min,
                steps=record.steps,
                resting_hr=record.resting_hr,
                synced_at=datetime.utcnow(),
            ))
        upserted_daily += 1

    upserted_vo2 = 0
    for record in payload.vo2max:
        existing = db.query(Vo2MaxLog).filter(Vo2MaxLog.date == record.date).first()
        if existing:
            existing.vo2max = record.vo2max
        else:
            db.add(Vo2MaxLog(date=record.date, vo2max=record.vo2max, source="garmin"))
        upserted_vo2 += 1

    db.commit()
    return {"upserted_daily": upserted_daily, "upserted_vo2": upserted_vo2}
