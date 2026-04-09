import uuid
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.engine import get_db
from database.models import WeeklyCheckin
from dependencies import get_user_id
from services import checkin_service

router = APIRouter(prefix="/api/checkin", tags=["checkin"])



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
    week_start: Optional[date] = None
    training_adherence: Optional[int] = None
    energy_level: Optional[int] = None
    sleep_quality: Optional[int] = None
    diet_adherence: Optional[int] = None
    stress_level: Optional[int] = None
    notes: Optional[str] = None


@router.post("")
def upsert_checkin(
    payload: CheckinUpsert,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    try:
        row = checkin_service.upsert_weekly_checkin(
            db,
            user_id,
            training_adherence=payload.training_adherence,
            energy_level=payload.energy_level,
            sleep_quality=payload.sleep_quality,
            diet_adherence=payload.diet_adherence,
            stress_level=payload.stress_level,
            notes=payload.notes,
            week_start=payload.week_start,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _checkin_dict(row)


@router.get("/latest")
def get_latest_checkin(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    row = db.query(WeeklyCheckin).filter(WeeklyCheckin.user_id == user_id).order_by(desc(WeeklyCheckin.week_start)).first()
    return _checkin_dict(row) if row else None


@router.get("/history")
def get_checkin_history(
    limit: int = 12,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    rows = (
        db.query(WeeklyCheckin)
        .filter(WeeklyCheckin.user_id == user_id)
        .order_by(desc(WeeklyCheckin.week_start))
        .limit(limit)
        .all()
    )
    return [_checkin_dict(r) for r in rows]
