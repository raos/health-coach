import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.engine import get_db
from database.models import DexaScan
from dependencies import get_user_id
from schemas.dexa import DexaScanCreate, DexaScanResponse

router = APIRouter(prefix="/api/dexa", tags=["dexa"])


@router.get("/latest", response_model=Optional[DexaScanResponse])
def get_latest_dexa(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    return db.query(DexaScan).filter(DexaScan.user_id == user_id).order_by(desc(DexaScan.scan_date)).first()


@router.get("/history", response_model=List[DexaScanResponse])
def get_dexa_history(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    return db.query(DexaScan).filter(DexaScan.user_id == user_id).order_by(desc(DexaScan.scan_date)).all()


@router.post("/scan", response_model=DexaScanResponse)
def create_dexa_scan(
    payload: DexaScanCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    scan = DexaScan(user_id=user_id, **payload.model_dump())
    db.add(scan)
    db.commit()
    db.refresh(scan)
    return scan


@router.get("/compare")
def compare_dexa_scans(
    scan_id_a: int,
    scan_id_b: int,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    a = db.query(DexaScan).filter(DexaScan.id == scan_id_a, DexaScan.user_id == user_id).first()
    b = db.query(DexaScan).filter(DexaScan.id == scan_id_b, DexaScan.user_id == user_id).first()
    if not a or not b:
        raise HTTPException(status_code=404, detail="Scan not found")

    return {
        "scan_a": DexaScanResponse.model_validate(a),
        "scan_b": DexaScanResponse.model_validate(b),
        "delta": {
            "total_weight_lbs": b.total_weight_lbs - a.total_weight_lbs,
            "body_fat_pct": b.body_fat_pct - a.body_fat_pct,
            "fat_mass_lbs": b.fat_mass_lbs - a.fat_mass_lbs,
            "lean_mass_lbs": b.lean_mass_lbs - a.lean_mass_lbs,
            "visceral_fat_lbs": (b.visceral_fat_lbs or 0) - (a.visceral_fat_lbs or 0),
        },
    }
