from datetime import date, datetime
from typing import Optional, List, Any
from pydantic import BaseModel


class TrainingPlanResponse(BaseModel):
    id: int
    generated_at: datetime
    week_start: date
    plan_json: str
    plan_markdown: Optional[str]
    context_hash: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}


class GenerateTrainingPlanRequest(BaseModel):
    strength_days: int = 4
    cardio_days: int = 2
    rest_days: int = 1


class ChatMessage(BaseModel):
    message: str
    session_id: str = "default"


class ChatHistoryItem(BaseModel):
    role: str
    content: str
