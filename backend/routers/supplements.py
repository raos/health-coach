import uuid
from datetime import date as date_type
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.engine import get_db
from database.models import Supplement, SupplementLog
from dependencies import get_user_id

router = APIRouter(prefix="/api/supplements", tags=["supplements"])


class SupplementCreate(BaseModel):
    name: str
    dosage: Optional[str] = None
    notes: Optional[str] = None


class SupplementUpdate(BaseModel):
    name: Optional[str] = None
    dosage: Optional[str] = None
    notes: Optional[str] = None


class SupplementLogCreate(BaseModel):
    supplement_id: int
    date: Optional[str] = None


def _supplement_dict(s: Supplement) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "dosage": s.dosage,
        "notes": s.notes,
        "is_active": s.is_active,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _log_dict(log: SupplementLog) -> dict:
    return {
        "id": log.id,
        "supplement_id": log.supplement_id,
        "date": log.date.isoformat(),
        "taken_at": log.taken_at.isoformat() if log.taken_at else None,
    }


@router.get("")
def list_supplements(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    return [
        _supplement_dict(s) for s in (
            db.query(Supplement)
            .filter(Supplement.user_id == user_id, Supplement.is_active == True)
            .order_by(Supplement.created_at)
            .all()
        )
    ]


@router.post("")
def create_supplement(
    payload: SupplementCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    s = Supplement(
        user_id=user_id,
        name=payload.name.strip(),
        dosage=payload.dosage.strip() if payload.dosage else None,
        notes=payload.notes.strip() if payload.notes else None,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _supplement_dict(s)


@router.patch("/{supplement_id}")
def update_supplement(
    supplement_id: int,
    payload: SupplementUpdate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    s = db.query(Supplement).filter(Supplement.id == supplement_id, Supplement.user_id == user_id, Supplement.is_active == True).first()
    if not s:
        raise HTTPException(status_code=404, detail="Supplement not found")
    if payload.name is not None:
        s.name = payload.name.strip()
    if payload.dosage is not None:
        s.dosage = payload.dosage.strip() or None
    if payload.notes is not None:
        s.notes = payload.notes.strip() or None
    db.commit()
    db.refresh(s)
    return _supplement_dict(s)


@router.delete("/{supplement_id}")
def delete_supplement(
    supplement_id: int,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    s = db.query(Supplement).filter(Supplement.id == supplement_id, Supplement.user_id == user_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Supplement not found")
    s.is_active = False
    db.commit()
    return {"status": "deleted", "id": supplement_id}


@router.get("/log")
def get_supplement_log(
    log_date: str = None,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    target = date_type.fromisoformat(log_date) if log_date else date_type.today()
    logs = (
        db.query(SupplementLog)
        .filter(SupplementLog.user_id == user_id, SupplementLog.date == target)
        .all()
    )
    return [_log_dict(log) for log in logs]


@router.post("/log")
def log_supplement_taken(
    payload: SupplementLogCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    s = db.query(Supplement).filter(
        Supplement.id == payload.supplement_id,
        Supplement.user_id == user_id,
        Supplement.is_active == True,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Supplement not found")

    target = date_type.fromisoformat(payload.date) if payload.date else date_type.today()

    existing = db.query(SupplementLog).filter(
        SupplementLog.user_id == user_id,
        SupplementLog.supplement_id == payload.supplement_id,
        SupplementLog.date == target,
    ).first()
    if existing:
        return _log_dict(existing)

    log = SupplementLog(user_id=user_id, supplement_id=payload.supplement_id, date=target)
    db.add(log)
    db.commit()
    db.refresh(log)
    return _log_dict(log)


@router.delete("/log/{log_id}")
def unlog_supplement(
    log_id: int,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    log = db.query(SupplementLog).filter(SupplementLog.id == log_id, SupplementLog.user_id == user_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log entry not found")
    db.delete(log)
    db.commit()
    return {"status": "deleted", "id": log_id}
