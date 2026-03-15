from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class DexaScanCreate(BaseModel):
    scan_date: date
    total_weight_lbs: float
    body_fat_pct: float
    fat_mass_lbs: float
    lean_mass_lbs: float
    bone_mass_lbs: Optional[float] = None
    visceral_fat_lbs: Optional[float] = None
    ag_ratio: Optional[float] = None
    almi: Optional[float] = None
    ffmi: Optional[float] = None
    t_score: Optional[float] = None
    facility: Optional[str] = None
    notes: Optional[str] = None
    raw_pdf_path: Optional[str] = None


class DexaScanResponse(BaseModel):
    id: int
    scan_date: date
    total_weight_lbs: float
    body_fat_pct: float
    fat_mass_lbs: float
    lean_mass_lbs: float
    bone_mass_lbs: Optional[float]
    visceral_fat_lbs: Optional[float]
    ag_ratio: Optional[float]
    almi: Optional[float]
    ffmi: Optional[float]
    t_score: Optional[float]
    facility: Optional[str]
    notes: Optional[str]
    raw_pdf_path: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
