import uuid
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.engine import get_db
from database.models import HealthInsight, DexaScan
from dependencies import get_user_id
from schemas.health import HealthInsightResponse
from services import claude_service

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/insights/latest", response_model=Optional[HealthInsightResponse])
def get_latest_insights(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    return (
        db.query(HealthInsight)
        .filter(HealthInsight.user_id == user_id, HealthInsight.insight_type == "weekly_summary")
        .order_by(desc(HealthInsight.generated_at))
        .first()
    )


@router.post("/insights", response_model=HealthInsightResponse)
def generate_insights(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    if not __import__("config").settings.anthropic_api_key:
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not configured.")

    content = claude_service.generate_health_insights(db, user_id=user_id)

    latest_dexa = (
        db.query(DexaScan)
        .filter(DexaScan.user_id == user_id)
        .order_by(desc(DexaScan.scan_date))
        .first()
    )

    insight = HealthInsight(
        user_id=user_id,
        insight_type="weekly_summary",
        content_md=content,
        data_snapshot=json.dumps({
            "body_fat_pct": latest_dexa.body_fat_pct if latest_dexa else None,
        }),
        is_read=False,
    )
    db.add(insight)
    db.commit()
    db.refresh(insight)
    return insight
