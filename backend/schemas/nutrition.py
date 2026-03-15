from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class MealPlanResponse(BaseModel):
    id: int
    generated_at: datetime
    week_start: date
    plan_json: str
    calorie_target: Optional[int]
    is_active: bool

    model_config = {"from_attributes": True}


class GenerateMealPlanRequest(BaseModel):
    calorie_target: Optional[int] = None
    breakfast_prefs: Optional[str] = None
    lunch_prefs: Optional[str] = None
    dinner_prefs: Optional[str] = None


class RegenerateDayRequest(BaseModel):
    day_of_week: str  # e.g. "Monday"
    plan_id: int
