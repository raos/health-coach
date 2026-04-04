import uuid
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.engine import get_db
from database.models import BodyCompositionLog, WeightLog
from dependencies import get_user_id
from schemas.body_composition import BodyCompositionLogCreate, BodyCompositionLogResponse

router = APIRouter(prefix="/api/body-composition", tags=["body-composition"])


@router.get("/latest", response_model=Optional[BodyCompositionLogResponse])
def get_latest(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    return (
        db.query(BodyCompositionLog)
        .filter(BodyCompositionLog.user_id == user_id)
        .order_by(desc(BodyCompositionLog.date))
        .first()
    )


@router.get("/history", response_model=List[BodyCompositionLogResponse])
def get_history(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    return (
        db.query(BodyCompositionLog)
        .filter(BodyCompositionLog.user_id == user_id)
        .order_by(desc(BodyCompositionLog.date))
        .all()
    )


@router.post("/log", response_model=BodyCompositionLogResponse)
def log_body_composition(
    payload: BodyCompositionLogCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    """Log a body composition reading. Derives lean/fat mass from weight if not provided."""
    bf = payload.body_fat_pct
    lean = payload.lean_mass_lbs
    fat = payload.fat_mass_lbs

    # Auto-derive lean/fat from latest weight if not provided
    if lean is None or fat is None:
        latest_weight = (
            db.query(WeightLog)
            .filter(WeightLog.user_id == user_id)
            .order_by(desc(WeightLog.date))
            .first()
        )
        if latest_weight:
            weight = latest_weight.weight_lbs
            fat = round(weight * (bf / 100), 1)
            lean = round(weight - fat, 1)

    entry = BodyCompositionLog(
        user_id=user_id,
        date=payload.date,
        body_fat_pct=bf,
        lean_mass_lbs=lean,
        fat_mass_lbs=fat,
        notes=payload.notes,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
