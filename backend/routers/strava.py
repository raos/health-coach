import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.engine import get_db
from dependencies import get_user_id
from services.strava_service import StravaService

router = APIRouter(prefix="/api/strava", tags=["strava"])


@router.get("/auth/url")
def get_auth_url(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    svc = StravaService(db, user_id)
    return {"url": svc.get_auth_url()}


@router.get("/status")
def get_status(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    svc = StravaService(db, user_id)
    return svc.get_status()


@router.delete("/disconnect")
def disconnect_strava(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    from database.models import OAuthToken
    token = db.query(OAuthToken).filter(
        OAuthToken.service == "strava",
        OAuthToken.user_id == user_id,
    ).first()
    if not token:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No Strava connection found.")
    db.delete(token)
    db.commit()
    return {"status": "disconnected"}
