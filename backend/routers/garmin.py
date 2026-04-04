import uuid
import json
from datetime import date, timedelta, datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.engine import get_db
from database.models import DailyHealthCache, Vo2MaxLog
from dependencies import get_user_id

router = APIRouter(prefix="/api/garmin", tags=["garmin"])


def _upsert_cache(db: Session, user_id: uuid.UUID, **kwargs) -> None:
    """Insert or update a DailyHealthCache row keyed by (user_id, date, source)."""
    row_date = kwargs.pop("date")
    source = kwargs.pop("source", "garmin")
    existing = db.query(DailyHealthCache).filter(
        DailyHealthCache.user_id == user_id,
        DailyHealthCache.date == row_date,
        DailyHealthCache.source == source,
    ).first()
    if existing:
        for k, v in kwargs.items():
            if v is not None:
                setattr(existing, k, v)
        existing.synced_at = datetime.utcnow()
    else:
        db.add(DailyHealthCache(user_id=user_id, date=row_date, source=source, synced_at=datetime.utcnow(), **kwargs))


@router.get("/sleep/range")
def get_sleep_range(
    days: int = 30,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    start = date.today() - timedelta(days=days)
    rows = (
        db.query(DailyHealthCache)
        .filter(
            DailyHealthCache.user_id == user_id,
            DailyHealthCache.date > start,
            DailyHealthCache.sleep_duration_hours.isnot(None),
        )
        .order_by(DailyHealthCache.date)
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
def get_steps_range(
    days: int = 30,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    start = date.today() - timedelta(days=days)
    rows = (
        db.query(DailyHealthCache)
        .filter(
            DailyHealthCache.user_id == user_id,
            DailyHealthCache.date > start,
            DailyHealthCache.steps.isnot(None),
        )
        .order_by(DailyHealthCache.date)
        .all()
    )
    return [{"date": r.date.isoformat(), "steps": r.steps} for r in rows]


@router.get("/resting-hr/range")
def get_resting_hr_range(
    days: int = 30,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    start = date.today() - timedelta(days=days)
    rows = (
        db.query(DailyHealthCache)
        .filter(
            DailyHealthCache.user_id == user_id,
            DailyHealthCache.date > start,
            DailyHealthCache.resting_hr.isnot(None),
        )
        .order_by(DailyHealthCache.date)
        .all()
    )
    return [{"date": r.date.isoformat(), "rhr": r.resting_hr} for r in rows]


# ── Paste-data endpoint (JWT auth, called from Settings UI) ───────────────────

def _extract_sleep_hours(data: dict, row_date: date) -> float | None:
    """
    Extract overnight sleep duration from bodyBatteryActivityEventList.
    Garmin's 'sleepingSeconds' only counts sleep within the midnight-to-midnight
    window of that calendar date, so it misses the pre-midnight portion of the
    previous night's sleep.  The bodyBattery SLEEP event captures the full episode.
    Falls back to sleepingSeconds if no suitable event is found.
    """
    events = data.get("bodyBatteryActivityEventList") or []
    best_hours = None
    prev_day = row_date - timedelta(days=1)

    for event in events:
        if event.get("eventType") != "SLEEP":
            continue
        duration_ms = event.get("durationInMilliseconds")
        if not duration_ms or duration_ms < 3_600_000:  # skip < 1 hour
            continue
        start_gmt_str = event.get("eventStartTimeGmt")
        tz_offset_ms = event.get("timezoneOffset") or 0
        if not start_gmt_str:
            continue
        try:
            start_gmt = datetime.fromisoformat(start_gmt_str)
            start_local = start_gmt + timedelta(milliseconds=tz_offset_ms)
        except ValueError:
            continue
        # Overnight sleep: started evening of prev_day (≥18:00) or early morning of row_date (<14:00)
        start_date = start_local.date()
        start_hour = start_local.hour
        is_overnight = (
            (start_date == prev_day and start_hour >= 18)
            or (start_date == row_date and start_hour < 14)
        )
        if is_overnight:
            hours = round(duration_ms / 3_600_000, 1)
            if best_hours is None or hours > best_hours:
                best_hours = hours

    if best_hours is not None:
        return best_hours
    # Fallback: sleepingSeconds (counts only the portion within this calendar day's window)
    sleeping_secs = data.get("sleepingSeconds")
    return round(sleeping_secs / 3600, 1) if sleeping_secs else None


class PasteDataRequest(BaseModel):
    json_data: str  # raw JSON string copied from Garmin Connect DevTools


@router.post("/paste-data")
def paste_data_from_ui(
    payload: PasteDataRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    """
    Parse a raw Garmin daily summary JSON (copied from DevTools) and upsert
    into DailyHealthCache. Accepts the usersummary format:
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
    sleep_duration_hours = _extract_sleep_hours(data, row_date)

    if steps is None and resting_hr is None and sleep_duration_hours is None:
        raise HTTPException(status_code=400, detail="No usable fields found (totalSteps, restingHeartRate, sleepingSeconds).")

    existing = db.query(DailyHealthCache).filter(
        DailyHealthCache.user_id == user_id,
        DailyHealthCache.date == row_date,
        DailyHealthCache.source == "garmin",
    ).first()
    if existing:
        if steps is not None:
            existing.steps = int(steps)
        if resting_hr is not None:
            existing.resting_hr = int(resting_hr)
        if sleep_duration_hours is not None:
            existing.sleep_duration_hours = sleep_duration_hours
        existing.synced_at = datetime.utcnow()
    else:
        db.add(DailyHealthCache(
            user_id=user_id,
            date=row_date,
            source="garmin",
            steps=int(steps) if steps is not None else None,
            resting_hr=int(resting_hr) if resting_hr is not None else None,
            sleep_duration_hours=sleep_duration_hours,
            synced_at=datetime.utcnow(),
        ))
    db.commit()

    return {
        "date": row_date.isoformat(),
        "steps": int(steps) if steps is not None else None,
        "resting_hr": int(resting_hr) if resting_hr is not None else None,
        "sleep_duration_hours": sleep_duration_hours,
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
    """
    from config import settings
    # Look up user by per-user MCP API key; fall back to global key for backwards compat
    from database.models import UserProfile as UP
    profile = db.query(UP).filter(UP.mcp_api_key == key).first()
    if not profile:
        if not settings.mcp_api_key or key != settings.mcp_api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        # Global key — default to admin user (backwards compat)
        from database.models import User
        admin_user = db.query(User).filter(User.is_admin == True, User.is_active == True).first()
        push_user_id = admin_user.id if admin_user else None
    else:
        push_user_id = profile.user_id

    if not push_user_id:
        raise HTTPException(status_code=401, detail="Could not identify user from API key")

    upserted_daily = 0
    for record in payload.daily:
        existing = db.query(DailyHealthCache).filter(
            DailyHealthCache.user_id == push_user_id,
            DailyHealthCache.date == record.date,
            DailyHealthCache.source == "garmin",
        ).first()
        if existing:
            for field in ("sleep_duration_hours", "sleep_score", "deep_min", "rem_min",
                          "light_min", "steps", "resting_hr"):
                val = getattr(record, field)
                if val is not None:
                    setattr(existing, field, val)
            existing.synced_at = datetime.utcnow()
        else:
            db.add(DailyHealthCache(
                user_id=push_user_id,
                date=record.date,
                source="garmin",
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
        existing = db.query(Vo2MaxLog).filter(
            Vo2MaxLog.user_id == push_user_id,
            Vo2MaxLog.date == record.date,
        ).first()
        if existing:
            existing.vo2max = record.vo2max
        else:
            db.add(Vo2MaxLog(user_id=push_user_id, date=record.date, vo2max=record.vo2max, source="garmin"))
        upserted_vo2 += 1

    db.commit()
    return {"upserted_daily": upserted_daily, "upserted_vo2": upserted_vo2}
