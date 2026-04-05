from datetime import date
from typing import Optional
from pydantic import BaseModel


class UserProfileResponse(BaseModel):
    id: int
    name: Optional[str] = ""
    dob: Optional[date] = None
    height_inches: Optional[float] = None
    email: Optional[str] = ""
    bf_goal_pct: Optional[float] = None
    vo2max_goal: Optional[float] = None
    goal_date: Optional[date] = None
    calorie_target: Optional[int] = None
    measurement_system: str = "imperial"
    training_device: str = "gym"
    breakfast_pref: Optional[str] = None
    lunch_pref: Optional[str] = None
    dinner_pref: Optional[str] = None
    # Multi-tenant fields
    mcp_api_key: Optional[str] = None
    hevy_api_key: Optional[str] = None
    training_days_strength: Optional[int] = 3
    training_days_cardio: Optional[int] = 2
    training_days_rest: Optional[int] = 2
    training_days_mobility: Optional[int] = 0
    preferred_exercises: Optional[str] = None
    exercises_to_avoid: Optional[str] = None
    dietary_preference: Optional[str] = "omnivore"
    preferred_cuisines: Optional[str] = None
    weekly_email_enabled: Optional[bool] = True
    weekly_email_cc: Optional[str] = None
    onboarding_complete: Optional[bool] = False

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
    breakfast_pref: Optional[str] = None
    lunch_pref: Optional[str] = None
    dinner_pref: Optional[str] = None
    hevy_api_key: Optional[str] = None
    training_days_strength: Optional[int] = None
    training_days_cardio: Optional[int] = None
    training_days_rest: Optional[int] = None
    training_days_mobility: Optional[int] = None
    preferred_exercises: Optional[str] = None
    exercises_to_avoid: Optional[str] = None
    dietary_preference: Optional[str] = None
    preferred_cuisines: Optional[str] = None
    weekly_email_enabled: Optional[bool] = None
    weekly_email_cc: Optional[str] = None
