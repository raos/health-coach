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
        raise HTTPException(status_code=401, detail=str(e))


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
