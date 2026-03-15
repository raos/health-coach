from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class HealthInsightResponse(BaseModel):
    id: int
    generated_at: datetime
    insight_type: str
    content_md: str
    is_read: bool

    model_config = {"from_attributes": True}


class Vo2MaxLogResponse(BaseModel):
    id: int
    date: str
    vo2max: float
    source: str

    model_config = {"from_attributes": True}
