from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class WeightLogCreate(BaseModel):
    date: date
    weight_lbs: float
    notes: Optional[str] = None
    source: str = "manual"


class WeightLogResponse(BaseModel):
    id: int
    date: date
    weight_lbs: float
    notes: Optional[str]
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}
