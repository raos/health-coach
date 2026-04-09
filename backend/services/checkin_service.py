import uuid
from datetime import date, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from database.models import WeeklyCheckin


def _monday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def upsert_weekly_checkin(
    db: Session,
    user_id: uuid.UUID,
    *,
    training_adherence: Optional[int] = None,
    energy_level: Optional[int] = None,
    sleep_quality: Optional[int] = None,
    diet_adherence: Optional[int] = None,
    stress_level: Optional[int] = None,
    notes: Optional[str] = None,
    week_start: Optional[date] = None,
) -> WeeklyCheckin:
    """
    Validate ratings (1-5) and upsert a WeeklyCheckin for the given week.
    Defaults to Monday of the current week if week_start is not provided.
    Raises ValueError if any rating is outside 1-5.
    """
    target_week = week_start or _monday_of_week(date.today())

    ratings = {
        "training_adherence": training_adherence,
        "energy_level": energy_level,
        "sleep_quality": sleep_quality,
        "diet_adherence": diet_adherence,
        "stress_level": stress_level,
    }
    for field, val in ratings.items():
        if val is not None and not (1 <= val <= 5):
            raise ValueError(f"{field} must be between 1 and 5")

    existing = db.query(WeeklyCheckin).filter(
        WeeklyCheckin.user_id == user_id,
        WeeklyCheckin.week_start == target_week,
    ).first()

    if existing:
        for field, val in ratings.items():
            if val is not None:
                setattr(existing, field, val)
        if notes is not None:
            existing.notes = notes
        db.commit()
        db.refresh(existing)
        return existing

    row = WeeklyCheckin(
        user_id=user_id,
        week_start=target_week,
        training_adherence=training_adherence,
        energy_level=energy_level,
        sleep_quality=sleep_quality,
        diet_adherence=diet_adherence,
        stress_level=stress_level,
        notes=notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
