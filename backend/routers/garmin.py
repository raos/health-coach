import json
import os
import time
from datetime import date
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.garmin_service import garmin_service

router = APIRouter(prefix="/api/garmin", tags=["garmin"])


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
    return {
        "configured": True,
        "authenticated": garmin_service.is_authenticated(),
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
    # Extend expires_at far into the future so garth never auto-refreshes.
    # garth's refresh hits connectapi.garmin.com/oauth-service/oauth/exchange
    # which returns an empty body from Railway's IP, causing a JSON parse error.
    # Garmin's server validates the actual access_token independently.
    oauth2 = dict(payload.oauth2)
    oauth2["expires_at"] = time.time() + 86400 * 365  # 1 year from now
    oauth2["refresh_token_expires_at"] = time.time() + 86400 * 365
    with open(os.path.join(token_dir, "oauth2_token.json"), "w") as f:
        json.dump(oauth2, f)
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
def get_sleep_range(days: int = 30):
    _require_auth()
    try:
        return garmin_service.get_sleep_range(days)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/steps/range")
def get_steps_range(days: int = 30):
    _require_auth()
    try:
        return garmin_service.get_steps_range(days)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/resting-hr/range")
def get_resting_hr_range(days: int = 30):
    _require_auth()
    try:
        return garmin_service.get_resting_hr_range(days)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


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
