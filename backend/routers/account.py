"""Account management endpoints: data export and account deletion."""
import io
import json
import uuid
import zipfile
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.engine import get_db
from database.models import (
    User, UserProfile, WeightLog, BodyCompositionLog, Vo2MaxLog, StravaActivity,
    HevyWorkout, HevyExerciseSet, TrainingPlan, MealPlan, NutritionLog,
    HealthInsight, CoachConversation, OAuthToken, GarminDailyCache,
    WeeklyCheckin, AuditLog
)
from dependencies import get_user_id, get_current_user

router = APIRouter(prefix="/api/account", tags=["account"])


def _to_dicts(rows, exclude_cols=None) -> list:
    """Convert SQLAlchemy rows to plain dicts, serializing dates/datetimes."""
    result = []
    for row in rows:
        d = {}
        for col in row.__table__.columns:
            if exclude_cols and col.name in exclude_cols:
                continue
            val = getattr(row, col.name)
            if hasattr(val, "isoformat"):
                val = val.isoformat()
            d[col.name] = val
        result.append(d)
    return result


@router.get("/data-export")
def export_data(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    """Generate a ZIP archive of all the user's data as JSON files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        def add(name: str, rows):
            data = _to_dicts(rows)
            zf.writestr(f"{name}.json", json.dumps(data, indent=2, default=str))

        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if profile:
            zf.writestr("profile.json", json.dumps(
                {c.name: getattr(profile, c.name)
                 for c in profile.__table__.columns if c.name not in ("hevy_api_key", "mcp_api_key")},
                indent=2,
                default=str,
            ))

        add("weight_logs", db.query(WeightLog).filter(WeightLog.user_id == user_id).all())
        add("body_composition_logs", db.query(BodyCompositionLog).filter(BodyCompositionLog.user_id == user_id).all())
        add("vo2max_logs", db.query(Vo2MaxLog).filter(Vo2MaxLog.user_id == user_id).all())
        add("strava_activities", db.query(StravaActivity).filter(StravaActivity.user_id == user_id).all())
        add("hevy_workouts", db.query(HevyWorkout).filter(HevyWorkout.user_id == user_id).all())
        add("nutrition_logs", db.query(NutritionLog).filter(NutritionLog.user_id == user_id).all())
        add("meal_plans", db.query(MealPlan).filter(MealPlan.user_id == user_id).all())
        add("training_plans", db.query(TrainingPlan).filter(TrainingPlan.user_id == user_id).all())
        add("health_insights", db.query(HealthInsight).filter(HealthInsight.user_id == user_id).all())
        add("weekly_checkins", db.query(WeeklyCheckin).filter(WeeklyCheckin.user_id == user_id).all())
        add("garmin_daily_cache", db.query(GarminDailyCache).filter(GarminDailyCache.user_id == user_id).all())
        add("coach_conversations", db.query(CoachConversation).filter(CoachConversation.user_id == user_id).all())

        readme = (
            "Health Coach Data Export\n"
            "========================\n"
            f"Exported: {datetime.now(timezone.utc).isoformat()} UTC\n\n"
            "Files:\n"
            "  profile.json          — Your profile settings and goals\n"
            "  weight_logs.json      — Daily weight entries\n"
            "  body_composition_logs.json — Body composition history\n"
            "  vo2max_logs.json      — VO2 max measurements\n"
            "  strava_activities.json— Synced cardio activities\n"
            "  hevy_workouts.json    — Synced strength training sessions\n"
            "  nutrition_logs.json   — Logged meals\n"
            "  meal_plans.json       — AI-generated meal plans\n"
            "  training_plans.json   — AI-generated training plans\n"
            "  health_insights.json  — AI-generated health insights\n"
            "  weekly_checkins.json  — Weekly self-assessment records\n"
            "  garmin_daily_cache.json — Garmin daily health metrics\n"
            "  coach_conversations.json — Coach and nutritionist chat history\n"
        )
        zf.writestr("README.txt", readme)

        db.add(AuditLog(user_id=user_id, action="data_export"))
        db.commit()

    buf.seek(0)
    filename = f"healthcoach_export_{datetime.now(timezone.utc).strftime('%Y%m%d')}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


class DeleteConfirmation(BaseModel):
    confirmation: str  # must equal "DELETE"


@router.delete("")
def delete_account(
    payload: DeleteConfirmation,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete the account: sets deleted_at on the User row.
    Hard purge runs 30 days later (manual or via scheduler).
    """
    if payload.confirmation != "DELETE":
        raise HTTPException(status_code=400, detail="Confirmation must be the string 'DELETE'.")

    current_user.deleted_at = datetime.now(timezone.utc)
    current_user.is_active = False
    db.add(AuditLog(user_id=current_user.id, action="account_delete_requested"))
    db.commit()
    return {"status": "ok", "message": "Account scheduled for deletion in 30 days."}


@router.delete("/conversations")
def clear_conversations(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    """Delete all coach/nutritionist chat history for this user."""
    deleted = db.query(CoachConversation).filter(CoachConversation.user_id == user_id).delete()
    db.add(AuditLog(user_id=user_id, action="clear_conversations", metadata_json={"deleted_count": deleted}))
    db.commit()
    return {"status": "ok", "deleted_count": deleted}
