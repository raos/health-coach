from datetime import date
from typing import Optional
from pydantic import BaseModel


class UserProfileResponse(BaseModel):
    id: int
    name: str
    dob: Optional[date]
    height_inches: Optional[float]
    email: str = ""
    bf_goal_pct: Optional[float]
    vo2max_goal: Optional[float]
    goal_date: Optional[date]
    calorie_target: Optional[int]
    measurement_system: str = "imperial"
    training_device: str = "tonal"
    training_plan_recipients: str = ""
    meal_plan_recipients: str = ""

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    dob: Optional[date] = None
    height_inches: Optional[float] = None
    email: Optional[str] = None
    bf_goal_pct: Optional[float] = None
    vo2max_goal: Optional[float] = None
    goal_date: Optional[date] = None
    calorie_target: Optional[int] = None
    measurement_system: Optional[str] = None
    training_device: Optional[str] = None
    training_plan_recipients: Optional[str] = None
    meal_plan_recipients: Optional[str] = None
