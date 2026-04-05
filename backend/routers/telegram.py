"""
Telegram bot router.

Public:
  POST /api/telegram/webhook   — Telegram calls this for every update

Protected (JWT via Depends(get_user_id)):
  GET    /api/telegram/status      — connection status for current user
  DELETE /api/telegram/disconnect  — unlink current user's Telegram account
"""
import asyncio
import hmac
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from config import settings
from database.engine import get_db
from database.models import UserProfile
from dependencies import get_user_id

router = APIRouter(prefix="/api/telegram", tags=["telegram"])
logger = logging.getLogger(__name__)


def _verify_secret(secret_token: Optional[str]) -> bool:
    """Validate Telegram's X-Telegram-Bot-Api-Secret-Token header if configured."""
    expected = settings.telegram_webhook_secret
    if not expected:
        return True  # skip validation in local dev when no secret is set
    if not secret_token:
        return False
    return hmac.compare_digest(secret_token.encode(), expected.encode())


# ── Public ────────────────────────────────────────────────────────────────────

@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
):
    """
    Telegram delivers every update here. Must return 200 within 5 seconds,
    so the actual processing runs as a background asyncio task.
    """
    if not _verify_secret(x_telegram_bot_api_secret_token):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    body = await request.body()
    try:
        update = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    from services.telegram_service import handle_update
    asyncio.create_task(handle_update(update))

    return {"ok": True}


# ── Protected (JWT enforced by Depends(get_user_id)) ─────────────────────────

@router.get("/status")
def get_telegram_status(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        return {"connected": False, "chat_id": None, "username": None, "connected_at": None}
    return {
        "connected": profile.telegram_chat_id is not None,
        "chat_id": profile.telegram_chat_id,
        "username": profile.telegram_username,
        "connected_at": (
            profile.telegram_connected_at.isoformat()
            if profile.telegram_connected_at else None
        ),
    }


@router.delete("/disconnect")
def disconnect_telegram(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile or not profile.telegram_chat_id:
        raise HTTPException(status_code=404, detail="No Telegram connection found.")
    profile.telegram_chat_id = None
    profile.telegram_username = None
    profile.telegram_connected_at = None
    db.commit()
    return {"status": "disconnected"}
