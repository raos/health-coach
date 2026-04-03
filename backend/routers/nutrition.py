import uuid
import json
from datetime import date as date_type, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.engine import get_db
from database.models import MealPlan, UserProfile, CoachConversation, NutritionLog
from dependencies import get_user_id
from pydantic import BaseModel
from schemas.nutrition import MealPlanResponse, RegenerateDayRequest, GenerateMealPlanRequest
from services import claude_service

router = APIRouter(prefix="/api/nutrition", tags=["nutrition"])


@router.get("/meal-plan/latest", response_model=Optional[MealPlanResponse])
def get_latest_meal_plan(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    return (
        db.query(MealPlan)
        .filter(MealPlan.user_id == user_id, MealPlan.is_active == True)
        .order_by(desc(MealPlan.generated_at))
        .first()
    )


@router.post("/meal-plan", response_model=MealPlanResponse)
def generate_meal_plan(
    payload: GenerateMealPlanRequest = GenerateMealPlanRequest(),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    if not __import__("config").settings.anthropic_api_key:
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not configured.")

    calorie_target = payload.calorie_target
    if not calorie_target:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        calorie_target = profile.calorie_target if profile and profile.calorie_target else None

    try:
        plan_data = claude_service.generate_meal_plan(
            db,
            user_id=user_id,
            calorie_target=calorie_target,
            breakfast_prefs=payload.breakfast_prefs,
            lunch_prefs=payload.lunch_prefs,
            dinner_prefs=payload.dinner_prefs,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    week_start_str = plan_data.get("week_start", str(date_type.today()))
    try:
        week_start = date_type.fromisoformat(week_start_str)
    except ValueError:
        week_start = date_type.today()

    calorie_target = plan_data.get("daily_target_kcal", 2000)

    db.query(MealPlan).filter(MealPlan.user_id == user_id).update({"is_active": False})

    plan = MealPlan(
        user_id=user_id,
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
def regenerate_day(
    payload: RegenerateDayRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    if not __import__("config").settings.anthropic_api_key:
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not configured.")

    plan = db.query(MealPlan).filter(MealPlan.id == payload.plan_id, MealPlan.user_id == user_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")

    current_data = json.loads(plan.plan_json)
    new_data = claude_service.generate_meal_plan(db, user_id=user_id)

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
def email_shopping_list(
    payload: ShoppingListEmailRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
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

        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        to_address = (profile.email or "").strip() if profile else ""
        cc_address = (profile.weekly_email_cc or "").strip() if profile else ""
        send_plan_email(
            to_address=to_address,
            subject="Grocery Shopping List",
            body_text=body,
            pdf_bytes=None,
            pdf_filename=None,
            cc_address=cc_address or None,
        )
        return {"status": "sent", "sent_to": to_address}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send email: {e}")


class LogMealRequest(BaseModel):
    description: str
    date: Optional[str] = None


@router.post("/log")
def log_meal_from_description(
    payload: LogMealRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    if not __import__("config").settings.anthropic_api_key:
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not configured.")

    try:
        parsed = claude_service.parse_meal_description(payload.description)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse meal description: {e}")

    target_date = date_type.fromisoformat(payload.date) if payload.date else date_type.today()

    entry = NutritionLog(
        user_id=user_id,
        date=target_date,
        meal_type=parsed.get("meal_type", "snack"),
        name=parsed.get("name", payload.description[:60]),
        description=payload.description,
        kcal=int(parsed.get("kcal", 0)),
        protein_g=float(parsed.get("protein_g", 0)),
        carbs_g=float(parsed.get("carbs_g", 0)),
        fat_g=float(parsed.get("fat_g", 0)),
        source="web",
        logged_at=datetime.utcnow(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    return {
        "id": entry.id,
        "date": entry.date.isoformat(),
        "meal_type": entry.meal_type,
        "name": entry.name,
        "description": entry.description,
        "kcal": entry.kcal,
        "protein_g": entry.protein_g,
        "carbs_g": entry.carbs_g,
        "fat_g": entry.fat_g,
        "source": entry.source,
        "logged_at": entry.logged_at.isoformat(),
    }


@router.get("/log")
def get_nutrition_log(
    log_date: str = Query(None, alias="date"),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    target = date_type.fromisoformat(log_date) if log_date else date_type.today()
    rows = (
        db.query(NutritionLog)
        .filter(NutritionLog.user_id == user_id, NutritionLog.date == target)
        .order_by(NutritionLog.logged_at)
        .all()
    )
    return [
        {
            "id": r.id,
            "date": r.date.isoformat(),
            "meal_type": r.meal_type,
            "name": r.name,
            "description": r.description,
            "kcal": r.kcal,
            "protein_g": r.protein_g,
            "carbs_g": r.carbs_g,
            "fat_g": r.fat_g,
            "source": r.source,
            "logged_at": r.logged_at.isoformat() if r.logged_at else None,
        }
        for r in rows
    ]


@router.delete("/log/{entry_id}")
def delete_nutrition_log_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    entry = db.query(NutritionLog).filter(NutritionLog.id == entry_id, NutritionLog.user_id == user_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()
    return {"ok": True}


@router.post("/email-plan")
def email_meal_plan(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    plan = (
        db.query(MealPlan)
        .filter(MealPlan.user_id == user_id, MealPlan.is_active == True)
        .order_by(desc(MealPlan.generated_at))
        .first()
    )
    if not plan or not plan.plan_json:
        raise HTTPException(status_code=404, detail="No meal plan found. Generate one first.")
    try:
        from services.email_service import generate_pdf, send_plan_email
        from services.claude_service import _meal_plan_to_markdown
        plan_data = json.loads(plan.plan_json)
        week = plan_data.get("week_start") or plan_data.get("week_label") or datetime.now().strftime("%Y-%m-%d")
        title = f"Meal Plan - {week}"
        markdown = _meal_plan_to_markdown(plan_data)
        pdf_bytes = generate_pdf(title, markdown)
        pdf_filename = f"meal_plan_{week.replace(', ', '_').replace(' ', '_')}.pdf"
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        to_address = (profile.email or "").strip() if profile else ""
        cc_address = (profile.weekly_email_cc or "").strip() if profile else ""
        send_plan_email(
            to_address=to_address,
            subject=title,
            body_text="Hi,\n\nThis week's meal plan is attached as a PDF.\n\nEnjoy!\n",
            pdf_bytes=pdf_bytes,
            pdf_filename=pdf_filename,
            cc_address=cc_address or None,
        )
        return {"status": "sent", "sent_to": to_address}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send email: {e}")


class NutritionChatMessage(BaseModel):
    message: str
    session_id: str = "nutrition-default"


@router.post("/chat")
def nutrition_chat(
    payload: NutritionChatMessage,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    if not __import__("config").settings.anthropic_api_key:
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not configured.")

    history_rows = (
        db.query(CoachConversation)
        .filter(
            CoachConversation.user_id == user_id,
            CoachConversation.session_id == payload.session_id,
        )
        .order_by(CoachConversation.created_at)
        .limit(20)
        .all()
    )
    history = [{"role": row.role, "content": row.content} for row in history_rows]

    response = claude_service.chat_with_nutritionist(payload.message, history, db, user_id=user_id)

    db.add(CoachConversation(user_id=user_id, session_id=payload.session_id, role="user", content=payload.message))
    db.add(CoachConversation(user_id=user_id, session_id=payload.session_id, role="assistant", content=response))
    db.commit()

    return {"response": response}


@router.delete("/chat/history")
def clear_nutrition_chat(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    db.query(CoachConversation).filter(
        CoachConversation.user_id == user_id,
        CoachConversation.session_id == "nutrition-default",
    ).delete()
    db.commit()
    return {"status": "cleared"}
