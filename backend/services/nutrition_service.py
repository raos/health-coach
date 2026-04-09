import uuid
from datetime import date, datetime
from sqlalchemy.orm import Session

from database.models import NutritionLog


def log_meal(
    db: Session,
    user_id: uuid.UUID,
    description: str,
    target_date: date = None,
    source: str = "mcp",
) -> NutritionLog:
    """Parse a free-text meal description with Claude and save to NutritionLog."""
    from services import claude_service

    parsed = claude_service.parse_meal_description(description)

    entry = NutritionLog(
        user_id=user_id,
        date=target_date or date.today(),
        meal_type=parsed.get("meal_type", "snack"),
        name=parsed.get("name", description[:60]),
        description=description,
        kcal=int(parsed.get("kcal", 0)),
        protein_g=float(parsed.get("protein_g", 0)),
        carbs_g=float(parsed.get("carbs_g", 0)),
        fat_g=float(parsed.get("fat_g", 0)),
        source=source,
        logged_at=datetime.utcnow(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
