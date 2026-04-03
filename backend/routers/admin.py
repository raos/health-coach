"""Admin-only endpoints for user management and system oversight."""
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.engine import get_db
from database.models import User, UserProfile, AuditLog
from dependencies import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _user_dict(user: User, profile: Optional[UserProfile]) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
        "auth_provider": user.auth_provider,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "onboarding_complete": profile.onboarding_complete if profile else False,
        "weekly_email_enabled": profile.weekly_email_enabled if profile else False,
        "training_device": profile.training_device if profile else None,
        "dietary_preference": profile.dietary_preference if profile else None,
        "invite_code_used": profile.invite_code_used if profile else None,
        "mcp_api_key": profile.mcp_api_key if profile else None,
    }


@router.get("/users")
def list_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all users with their profile summaries."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    result = []
    for user in users:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
        result.append(_user_dict(user, profile))
    return result


class UserUpdate(BaseModel):
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


@router.patch("/users/{user_id}")
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Toggle is_active or is_admin on a user."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot modify your own admin account.")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.is_admin is not None:
        user.is_admin = payload.is_admin
    db.add(AuditLog(
        user_id=admin.id,
        action="admin_user_update",
        metadata_json={"target_user_id": str(user_id), "changes": payload.model_dump(exclude_none=True)},
    ))
    db.commit()
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    return _user_dict(user, profile)


@router.get("/audit-log")
def get_audit_log(
    limit: int = 100,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Recent audit log entries."""
    entries = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(e.id),
            "user_id": str(e.user_id) if e.user_id else None,
            "action": e.action,
            "ip_address": e.ip_address,
            "metadata": e.metadata_json,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entries
    ]


@router.get("/stats")
def get_stats(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """High-level usage stats."""
    from database.models import (
        MealPlan, TrainingPlan, NutritionLog, OAuthToken,
        HevyWorkout, StravaActivity
    )
    return {
        "total_users": db.query(User).count(),
        "active_users": db.query(User).filter(User.is_active == True).count(),
        "onboarded_users": db.query(UserProfile).filter(UserProfile.onboarding_complete == True).count(),
        "total_meal_plans": db.query(MealPlan).count(),
        "total_training_plans": db.query(TrainingPlan).count(),
        "total_nutrition_logs": db.query(NutritionLog).count(),
        "strava_connected": db.query(OAuthToken).filter(OAuthToken.service == "strava").count(),
        "hevy_connected": db.query(UserProfile).filter(UserProfile.hevy_api_key != None).count(),
        "total_workouts": db.query(HevyWorkout).count(),
        "total_strava_activities": db.query(StravaActivity).count(),
    }
