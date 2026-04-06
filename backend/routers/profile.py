import uuid
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.engine import get_db
from database.models import UserProfile
from dependencies import get_user_id
from schemas.profile import UserProfileResponse, UserProfileUpdate

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _get_or_create_profile(db: Session, user_id: uuid.UUID) -> UserProfile:
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        profile = UserProfile(user_id=user_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.get("", response_model=UserProfileResponse)
def get_profile(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    return _get_or_create_profile(db, user_id)


@router.put("", response_model=UserProfileResponse)
def update_profile(
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    profile = _get_or_create_profile(db, user_id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/onboarding-status")
def get_onboarding_status(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    return {"onboarding_complete": profile.onboarding_complete if profile else False}


@router.post("/generate-mcp-key")
def generate_mcp_key(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    """Generate (or regenerate) the per-user MCP API key."""
    from database.encryption import hmac_lookup as _hmac_lookup
    profile = _get_or_create_profile(db, user_id)
    _new_mcp_key = str(uuid.uuid4())
    profile.mcp_api_key = _new_mcp_key
    profile.mcp_api_key_lookup = _hmac_lookup(_new_mcp_key)
    db.commit()
    return {"mcp_api_key": profile.mcp_api_key}


@router.post("/complete-onboarding")
def complete_onboarding(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    profile = _get_or_create_profile(db, user_id)
    profile.onboarding_complete = True
    if not profile.mcp_api_key:
        from database.encryption import hmac_lookup as _hmac_lookup
        _new_mcp_key = str(uuid.uuid4())
        profile.mcp_api_key = _new_mcp_key
        profile.mcp_api_key_lookup = _hmac_lookup(_new_mcp_key)
    db.commit()

    # Issue a refreshed JWT with onboarding_complete=True
    from database.models import User
    from routers.auth import _issue_jwt
    user = db.query(User).filter(User.id == user_id).first()
    new_token = _issue_jwt(user, db) if user else None
    return {"status": "ok", "onboarding_complete": True, "token": new_token}
