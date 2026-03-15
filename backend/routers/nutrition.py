import json
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.engine import get_db
from database.models import MealPlan
from schemas.nutrition import MealPlanResponse, RegenerateDayRequest, GenerateMealPlanRequest
from services import claude_service

router = APIRouter(prefix="/api/nutrition", tags=["nutrition"])


@router.get("/meal-plan/latest", response_model=Optional[MealPlanResponse])
def get_latest_meal_plan(db: Session = Depends(get_db)):
    plan = db.query(MealPlan).filter(MealPlan.is_active == True).order_by(desc(MealPlan.generated_at)).first()
    return plan


@router.post("/meal-plan", response_model=MealPlanResponse)
def generate_meal_plan(payload: GenerateMealPlanRequest = GenerateMealPlanRequest(), db: Session = Depends(get_db)):
    if not __import__("config").settings.anthropic_api_key:
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not configured. Add it to your .env file.")

    try:
        plan_data = claude_service.generate_meal_plan(
            db,
            calorie_target=payload.calorie_target,
            breakfast_prefs=payload.breakfast_prefs,
            lunch_prefs=payload.lunch_prefs,
            dinner_prefs=payload.dinner_prefs,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    week_start_str = plan_data.get("week_start", str(date.today()))
    try:
        week_start = date.fromisoformat(week_start_str)
    except ValueError:
        week_start = date.today()

    calorie_target = plan_data.get("daily_target_kcal", 2200)

    # Deactivate old plans
    db.query(MealPlan).update({"is_active": False})

    plan = MealPlan(
        week_start=week_start,
        plan_json=json.dumps(plan_data),
        calorie_target=calorie_target,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/meal-plan/regenerate-day", response_model=MealPlanResponse)
def regenerate_day(payload: RegenerateDayRequest, db: Session = Depends(get_db)):
    if not __import__("config").settings.anthropic_api_key:
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not configured.")

    plan = db.query(MealPlan).filter(MealPlan.id == payload.plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")

    current_data = json.loads(plan.plan_json)

    # Re-generate just the requested day
    from services.claude_service import generate_meal_plan as gen_full
    new_data = gen_full(db)

    # Swap the day
    day_map = {d["day"]: d for d in new_data.get("days", [])}
    existing_days = current_data.get("days", [])
    for i, day in enumerate(existing_days):
        if day["day"] == payload.day_of_week and payload.day_of_week in day_map:
            existing_days[i] = day_map[payload.day_of_week]
            break

    current_data["days"] = existing_days
    plan.plan_json = json.dumps(current_data)
    db.commit()
    db.refresh(plan)
    return plan
