from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database.engine import get_db
from services.strava_service import StravaService

router = APIRouter(prefix="/api/strava", tags=["strava"])


@router.get("/auth/url")
def get_auth_url(db: Session = Depends(get_db)):
    svc = StravaService(db)
    return {"url": svc.get_auth_url()}



@router.get("/status")
def get_status(db: Session = Depends(get_db)):
    svc = StravaService(db)
    return svc.get_status()
