import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.engine import get_db
from dependencies import get_user_id

router = APIRouter(prefix="/api/email", tags=["email"])


@router.post("/weekly-summary")
def trigger_weekly_summary(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    """Manually send the weekly health summary email for the requesting user."""
    from services.weekly_summary_service import send_weekly_summary_for_user
    send_weekly_summary_for_user(user_id=user_id, db=db)
    return {"status": "sent"}
