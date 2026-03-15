import json
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.engine import get_db
from database.models import TrainingPlan, CoachConversation
from schemas.coach import TrainingPlanResponse, ChatMessage, GenerateTrainingPlanRequest
from services import claude_service

router = APIRouter(prefix="/api/coach", tags=["coach"])


@router.get("/training-plan/latest", response_model=Optional[TrainingPlanResponse])
def get_latest_plan(db: Session = Depends(get_db)):
    plan = db.query(TrainingPlan).filter(TrainingPlan.is_active == True).order_by(desc(TrainingPlan.generated_at)).first()
    return plan


@router.post("/training-plan", response_model=TrainingPlanResponse)
def generate_training_plan(
    payload: GenerateTrainingPlanRequest = GenerateTrainingPlanRequest(),
    db: Session = Depends(get_db),
):
    if not __import__("config").settings.anthropic_api_key:
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not configured. Add it to your .env file.")

    context_hash = claude_service.build_context_hash(db)
    # Include schedule config in the hash so changing days forces a regen
    config_str = f"{payload.strength_days}s{payload.cardio_days}c{payload.rest_days}r"
    context_hash = context_hash + config_str

    existing = (
        db.query(TrainingPlan)
        .filter(TrainingPlan.context_hash == context_hash, TrainingPlan.is_active == True)
        .order_by(desc(TrainingPlan.generated_at))
        .first()
    )
    if existing:
        return existing

    try:
        plan_data = claude_service.generate_training_plan(
            db,
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

    # Deactivate old plans
    db.query(TrainingPlan).update({"is_active": False})

    plan = TrainingPlan(
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
def coach_chat(payload: ChatMessage, db: Session = Depends(get_db)):
    if not __import__("config").settings.anthropic_api_key:
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not configured.")

    # Get recent conversation history
    history_rows = (
        db.query(CoachConversation)
        .filter(CoachConversation.session_id == payload.session_id)
        .order_by(CoachConversation.created_at)
        .limit(20)
        .all()
    )
    history = [{"role": row.role, "content": row.content} for row in history_rows]

    response = claude_service.chat_with_coach(payload.message, history, db)

    # Save both turns
    db.add(CoachConversation(session_id=payload.session_id, role="user", content=payload.message))
    db.add(CoachConversation(session_id=payload.session_id, role="assistant", content=response))
    db.commit()

    return {"response": response}


@router.post("/sync")
def sync_activities(db: Session = Depends(get_db)):
    """Trigger Strava + Hevy data sync."""
    results = {"strava": "skipped", "hevy": "skipped"}

    # Try Strava sync
    try:
        from services.strava_service import StravaService
        svc = StravaService(db)
        if svc.is_connected():
            r = svc.sync_activities()
            results["strava"] = f"+{r['added']} added, {r['updated']} updated, {r['deleted']} deleted"
    except Exception as e:
        results["strava"] = f"error: {str(e)}"

    # Try Hevy sync
    try:
        import services.hevy_service as hevy_svc
        if hevy_svc.is_configured():
            r = hevy_svc.sync_workouts(db)
            results["hevy"] = f"+{r['added']} added, {r['updated']} updated, {r['deleted']} deleted"
    except Exception as e:
        results["hevy"] = f"error: {str(e)}"

    return results


@router.post("/email-plan")
def email_training_plan(db: Session = Depends(get_db)):
    """Generate a PDF of the latest training plan and email it to Sandeep."""
    plan = db.query(TrainingPlan).filter(TrainingPlan.is_active == True).order_by(desc(TrainingPlan.generated_at)).first()
    if not plan or not plan.plan_json:
        raise HTTPException(status_code=404, detail="No training plan found. Generate one first.")
    try:
        from services.email_service import generate_pdf, send_plan_email
        from services.claude_service import _training_plan_to_markdown
        from datetime import datetime
        plan_data = json.loads(plan.plan_json)
        week = plan.week_start.strftime("%b %d, %Y") if plan.week_start else datetime.now().strftime("%b %d, %Y")
        title = f"Training Plan — Week of {week}"
        markdown = _training_plan_to_markdown(plan_data)
        pdf_bytes = generate_pdf(title, markdown)
        send_plan_email(
            to_addresses=["m.sandeep.rao@gmail.com"],
            subject=title,
            body_text=f"Hi Sandeep,\n\nYour training plan for the week of {week} is attached as a PDF.\n\nStay consistent!\n",
            pdf_bytes=pdf_bytes,
            pdf_filename=f"training_plan_{week.replace(', ', '_').replace(' ', '_')}.pdf",
        )
        return {"status": "sent", "to": ["m.sandeep.rao@gmail.com"]}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send email: {e}")
