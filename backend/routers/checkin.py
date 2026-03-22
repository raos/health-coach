from datetime import date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.engine import get_db
from database.models import WeeklyCheckin

router = APIRouter(prefix="/api/checkin", tags=["checkin"])


def _monday_of_week(d: date) -> date:
    """Return the Monday of the week containing d."""
    return d - timedelta(days=d.weekday())


def _checkin_dict(c: WeeklyCheckin) -> dict:
    return {
        "id": c.id,
        "week_start": str(c.week_start),
        "training_adherence": c.training_adherence,
        "energy_level": c.energy_level,
        "sleep_quality": c.sleep_quality,
        "diet_adherence": c.diet_adherence,
        "stress_level": c.stress_level,
        "notes": c.notes,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat() if c.updated_at else c.created_at.isoformat(),
    }


class CheckinUpsert(BaseModel):
    week_start: Optional[date] = None   # defaults to current week's Monday
    training_adherence: Optional[int] = None
    energy_level: Optional[int] = None
    sleep_quality: Optional[int] = None
    diet_adherence: Optional[int] = None
    stress_level: Optional[int] = None
    notes: Optional[str] = None


@router.post("")
def upsert_checkin(payload: CheckinUpsert, db: Session = Depends(get_db)):
    """Create or update the check-in for the given week (defaults to current week)."""
    week_start = payload.week_start or _monday_of_week(date.today())

    # Validate 1–5 ranges
    for field in ("training_adherence", "energy_level", "sleep_quality", "diet_adherence", "stress_level"):
        val = getattr(payload, field)
        if val is not None and not (1 <= val <= 5):
            raise HTTPException(status_code=422, detail=f"{field} must be between 1 and 5")

    existing = db.query(WeeklyCheckin).filter(WeeklyCheckin.week_start == week_start).first()
    if existing:
        for field in ("training_adherence", "energy_level", "sleep_quality", "diet_adherence", "stress_level", "notes"):
            val = getattr(payload, field)
            if val is not None:
                setattr(existing, field, val)
        db.commit()
        db.refresh(existing)
        return _checkin_dict(existing)

    row = WeeklyCheckin(
        week_start=week_start,
        training_adherence=payload.training_adherence,
        energy_level=payload.energy_level,
        sleep_quality=payload.sleep_quality,
        diet_adherence=payload.diet_adherence,
        stress_level=payload.stress_level,
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _checkin_dict(row)


@router.get("/latest")
def get_latest_checkin(db: Session = Depends(get_db)):
    row = db.query(WeeklyCheckin).order_by(desc(WeeklyCheckin.week_start)).first()
    if not row:
        return None
    return _checkin_dict(row)


@router.get("/history")
def get_checkin_history(limit: int = 12, db: Session = Depends(get_db)):
    rows = (
        db.query(WeeklyCheckin)
        .order_by(desc(WeeklyCheckin.week_start))
        .limit(limit)
        .all()
    )
    return [_checkin_dict(r) for r in rows]
