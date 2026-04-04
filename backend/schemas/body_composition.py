from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class BodyCompositionLogCreate(BaseModel):
    date: date
    body_fat_pct: float
    lean_mass_lbs: Optional[float] = None
    fat_mass_lbs: Optional[float] = None
    notes: Optional[str] = None


class BodyCompositionLogResponse(BaseModel):
    id: int
    date: date
    body_fat_pct: float
    lean_mass_lbs: Optional[float]
    fat_mass_lbs: Optional[float]
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
