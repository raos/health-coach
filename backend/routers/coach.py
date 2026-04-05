import uuid
import json
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.engine import get_db
from database.models import TrainingPlan, CoachConversation, UserProfile
from dependencies import get_user_id
from schemas.coach import TrainingPlanResponse, ChatMessage, GenerateTrainingPlanRequest
from services import claude_service

router = APIRouter(prefix="/api/coach", tags=["coach"])


@router.get("/training-plan/latest", response_model=Optional[TrainingPlanResponse])
def get_latest_plan(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    return (
        db.query(TrainingPlan)
        .filter(TrainingPlan.user_id == user_id, TrainingPlan.is_active == True)
        .order_by(desc(TrainingPlan.generated_at))
        .first()
    )


@router.post("/training-plan", response_model=TrainingPlanResponse)
def generate_training_plan(
    payload: GenerateTrainingPlanRequest = GenerateTrainingPlanRequest(),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    if not __import__("config").settings.anthropic_api_key:
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not configured.")

    context_hash = claude_service.build_context_hash(db, user_id=user_id)
    config_str = f"{payload.strength_days}s{payload.cardio_days}c{payload.rest_days}r"
    context_hash = str(user_id)[:8] + "_" + context_hash + config_str

    if not payload.force:
        existing = (
            db.query(TrainingPlan)
            .filter(
                TrainingPlan.user_id == user_id,
                TrainingPlan.context_hash == context_hash,
                TrainingPlan.is_active == True,
            )
            .order_by(desc(TrainingPlan.generated_at))
            .first()
        )
        if existing:
            return existing

    try:
        plan_data = claude_service.generate_training_plan(
            db,
            user_id=user_id,
            strength_days=payload.strength_days,
            cardio_days=payload.cardio_days,
            rest_days=payload.rest_days,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    week_start_str = plan_data.get("week_start", str(date.today()))
    try:
        week_start = date.fromisoformat(week_start_str)
    except ValueError:
        week_start = date.today()

    # Deactivate old plans for this user only
    db.query(TrainingPlan).filter(TrainingPlan.user_id == user_id).update({"is_active": False})

    plan = TrainingPlan(
        user_id=user_id,
        week_start=week_start,
        plan_json=json.dumps(plan_data),
        context_hash=context_hash,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/chat")
def coach_chat(
    payload: ChatMessage,
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

    response = claude_service.chat_with_coach(payload.message, history, db, user_id=user_id)

    db.add(CoachConversation(user_id=user_id, session_id=payload.session_id, role="user", content=payload.message))
    db.add(CoachConversation(user_id=user_id, session_id=payload.session_id, role="assistant", content=response))
    db.commit()

    return {"response": response}


@router.post("/sync")
def sync_activities(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    results = {"strava": "skipped", "hevy": "skipped"}

    try:
        from services.strava_service import StravaService
        svc = StravaService(db, user_id=user_id)
        if svc.is_connected():
            r = svc.sync_activities()
            results["strava"] = f"+{r['added']} added, {r['updated']} updated, {r['deleted']} deleted"
    except Exception as e:
        results["strava"] = f"error: {str(e)}"

    try:
        import services.hevy_service as hevy_svc
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        api_key = profile.hevy_api_key if profile else None
        if api_key:
            r = hevy_svc.sync_workouts(db, user_id=user_id, api_key=api_key)
            results["hevy"] = f"+{r['added']} added, {r['updated']} updated, {r['deleted']} deleted"
    except Exception as e:
        results["hevy"] = f"error: {str(e)}"

    return results


@router.post("/email-plan")
def email_training_plan(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    plan = (
        db.query(TrainingPlan)
        .filter(TrainingPlan.user_id == user_id, TrainingPlan.is_active == True)
        .order_by(desc(TrainingPlan.generated_at))
        .first()
    )
    if not plan or not plan.plan_json:
        raise HTTPException(status_code=404, detail="No training plan found. Generate one first.")
    try:
        from services.email_service import generate_pdf, send_plan_email
        from services.claude_service import _training_plan_to_markdown
        from datetime import datetime
        plan_data = json.loads(plan.plan_json)
        week = plan.week_start.strftime("%b %d, %Y") if plan.week_start else datetime.now().strftime("%b %d, %Y")
        title = f"Training Plan - Week of {week}"
        markdown = _training_plan_to_markdown(plan_data)
        pdf_bytes = generate_pdf(title, markdown)
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        to_address = (profile.email or "").strip() if profile else ""
        send_plan_email(
            to_address=to_address,
            subject=title,
            body_text=f"Hi,\n\nYour training plan for the week of {week} is attached as a PDF.\n\nStay consistent!\n",
            pdf_bytes=pdf_bytes,
            pdf_filename=f"training_plan_{week.replace(', ', '_').replace(' ', '_')}.pdf",
        )
        return {"status": "sent", "to": to_address}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send email: {e}")
