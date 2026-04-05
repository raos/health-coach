import uuid
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.engine import get_db
from database.models import WeightLog
from dependencies import get_user_id
from schemas.weight import WeightLogCreate, WeightLogResponse

router = APIRouter(prefix="/api/weight", tags=["weight"])


@router.post("/log", response_model=WeightLogResponse)
def log_weight(
    payload: WeightLogCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    existing = db.query(WeightLog).filter(
        WeightLog.user_id == user_id,
        WeightLog.date == payload.date,
    ).first()
    if existing:
        existing.weight_lbs = payload.weight_lbs
        existing.notes = payload.notes
        existing.source = payload.source
        db.commit()
        db.refresh(existing)
        return existing

    entry = WeightLog(user_id=user_id, **payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/latest", response_model=Optional[WeightLogResponse])
def get_latest_weight(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    return db.query(WeightLog).filter(WeightLog.user_id == user_id).order_by(desc(WeightLog.date)).first()


@router.get("/history", response_model=List[WeightLogResponse])
def get_weight_history(
    start: Optional[date] = None,
    end: Optional[date] = None,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    q = db.query(WeightLog).filter(WeightLog.user_id == user_id)
    if start:
        q = q.filter(WeightLog.date >= start)
    if end:
        q = q.filter(WeightLog.date <= end)
    return q.order_by(WeightLog.date).all()


@router.delete("/{entry_id}")
def delete_weight_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    entry = db.query(WeightLog).filter(WeightLog.id == entry_id, WeightLog.user_id == user_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()
    return {"ok": True}
