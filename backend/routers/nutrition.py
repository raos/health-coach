import json
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.engine import get_db
from database.models import MealPlan, UserProfile
from pydantic import BaseModel
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

    # If calorie_target not provided (None or 0), fall back to profile value
    calorie_target = payload.calorie_target
    if not calorie_target:
        profile = db.query(UserProfile).first()
        calorie_target = profile.calorie_target if profile and profile.calorie_target else None

    try:
        plan_data = claude_service.generate_meal_plan(
            db,
            calorie_target=calorie_target,
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


class ShoppingListEmailRequest(BaseModel):
    items: dict[str, list[str]]


@router.post("/email-shopping-list")
def email_shopping_list(payload: ShoppingListEmailRequest, db: Session = Depends(get_db)):
    """Email checked shopping list items to Sandeep and Preetha."""
    if not payload.items:
        raise HTTPException(status_code=400, detail="No items provided.")
    try:
        from services.email_service import send_plan_email

        lines = ["Here are the groceries you need to pick up:\n"]
        for category, items in payload.items.items():
            if items:
                lines.append(f"{category.upper()}")
                for item in items:
                    lines.append(f"  - {item}")
                lines.append("")

        body = "\n".join(lines)

        sent, errors = [], []
        for address in ["m.sandeep.rao@gmail.com", "preetha.s.rao@gmail.com"]:
            try:
                send_plan_email(
                    to_address=address,
                    subject="Grocery Shopping List",
                    body_text=body,
                    pdf_bytes=None,
                    pdf_filename=None,
                )
                sent.append(address)
            except Exception as e:
                errors.append(f"{address}: {e}")
        if not sent:
            raise RuntimeError("; ".join(errors))
        return {"status": "sent", "sent_to": sent}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send email: {e}")


@router.post("/email-plan")
def email_meal_plan(db: Session = Depends(get_db)):
    """Generate a PDF of the latest meal plan and email it to Sandeep and Preetha."""
    plan = db.query(MealPlan).filter(MealPlan.is_active == True).order_by(desc(MealPlan.generated_at)).first()
    if not plan or not plan.plan_json:
        raise HTTPException(status_code=404, detail="No meal plan found. Generate one first.")
    try:
        from services.email_service import generate_pdf, send_plan_email
        from services.claude_service import _meal_plan_to_markdown
        from datetime import datetime
        plan_data = json.loads(plan.plan_json)
        week = plan_data.get("week_start") or plan_data.get("week_label") or datetime.now().strftime("%Y-%m-%d")
        title = f"Meal Plan - {week}"
        markdown = _meal_plan_to_markdown(plan_data)
        pdf_bytes = generate_pdf(title, markdown)
        pdf_filename = f"meal_plan_{week.replace(', ', '_').replace(' ', '_')}.pdf"
        sent, errors = [], []
        for address in ["m.sandeep.rao@gmail.com", "preetha.s.rao@gmail.com"]:
            try:
                send_plan_email(
                    to_address=address,
                    subject=title,
                    body_text="Hi,\n\nThis week's meal plan is attached as a PDF.\n\nEnjoy!\n",
                    pdf_bytes=pdf_bytes,
                    pdf_filename=pdf_filename,
                )
                sent.append(address)
            except Exception as e:
                errors.append(f"{address}: {e}")
        if not sent:
            raise RuntimeError("; ".join(errors))
        return {"status": "sent", "sent_to": sent}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send email: {e}")
