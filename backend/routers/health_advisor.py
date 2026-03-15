import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.engine import get_db
from database.models import HealthInsight
from schemas.health import HealthInsightResponse
from services import claude_service

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/insights/latest", response_model=Optional[HealthInsightResponse])
def get_latest_insights(db: Session = Depends(get_db)):
    insight = (
        db.query(HealthInsight)
        .filter(HealthInsight.insight_type == "weekly_summary")
        .order_by(desc(HealthInsight.generated_at))
        .first()
    )
    return insight


@router.post("/insights", response_model=HealthInsightResponse)
def generate_insights(db: Session = Depends(get_db)):
    if not __import__("config").settings.anthropic_api_key:
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not configured. Add it to your .env file.")

    content = claude_service.generate_health_insights(db)

    # Capture the data snapshot used
    latest_dexa = db.query(__import__("database.models", fromlist=["DexaScan"]).DexaScan).order_by(desc(__import__("database.models", fromlist=["DexaScan"]).DexaScan.scan_date)).first()

    insight = HealthInsight(
        insight_type="weekly_summary",
        content_md=content,
        data_snapshot=json.dumps({
            "body_fat_pct": latest_dexa.body_fat_pct if latest_dexa else 28.4,
        }),
        is_read=False,
    )
    db.add(insight)
    db.commit()
    db.refresh(insight)
    return insight
