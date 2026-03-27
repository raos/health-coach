from fastapi import APIRouter
from services.weekly_summary_service import send_weekly_summary

router = APIRouter(prefix="/api/email", tags=["email"])


@router.post("/weekly-summary")
def trigger_weekly_summary():
    """Manually send the weekly health summary email."""
    send_weekly_summary()
    return {"status": "sent"}
