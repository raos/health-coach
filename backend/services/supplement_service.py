import uuid
from datetime import date
from typing import Optional
from sqlalchemy.orm import Session

from database.models import Supplement, SupplementLog


def log_supplement_by_name(
    db: Session,
    user_id: uuid.UUID,
    name: str,
    target_date: Optional[date] = None,
) -> tuple:
    """
    Case-insensitive lookup of supplement by name. Auto-creates if not found.
    Returns (log_entry, already_existed, supplement, supplement_was_created).
    - log_entry is None if already_existed is True.
    - supplement_was_created is True if the supplement row was just inserted.
    """
    target_date = target_date or date.today()

    supplements = (
        db.query(Supplement)
        .filter(Supplement.user_id == user_id, Supplement.is_active == True)
        .all()
    )
    match = next((s for s in supplements if s.name.lower() == name.lower()), None)

    supplement_created = False
    if not match:
        match = Supplement(user_id=user_id, name=name)
        db.add(match)
        db.commit()
        db.refresh(match)
        supplement_created = True

    existing = db.query(SupplementLog).filter(
        SupplementLog.user_id == user_id,
        SupplementLog.supplement_id == match.id,
        SupplementLog.date == target_date,
    ).first()

    if existing:
        return (None, True, match, supplement_created)

    log = SupplementLog(user_id=user_id, supplement_id=match.id, date=target_date)
    db.add(log)
    db.commit()
    db.refresh(log)
    return (log, False, match, supplement_created)


def log_supplement_by_id(
    db: Session,
    user_id: uuid.UUID,
    supplement_id: int,
    target_date: Optional[date] = None,
) -> tuple:
    """
    Log a supplement by its ID. Does not auto-create.
    Returns (log_entry, already_existed, supplement).
    Returns None for supplement if not found (caller should handle as 404).
    """
    target_date = target_date or date.today()

    supplement = db.query(Supplement).filter(
        Supplement.id == supplement_id,
        Supplement.user_id == user_id,
        Supplement.is_active == True,
    ).first()
    if not supplement:
        return (None, False, None)

    existing = db.query(SupplementLog).filter(
        SupplementLog.user_id == user_id,
        SupplementLog.supplement_id == supplement_id,
        SupplementLog.date == target_date,
    ).first()

    if existing:
        return (existing, True, supplement)

    log = SupplementLog(user_id=user_id, supplement_id=supplement_id, date=target_date)
    db.add(log)
    db.commit()
    db.refresh(log)
    return (log, False, supplement)


def get_supplement_status_for_date(
    db: Session,
    user_id: uuid.UUID,
    target_date: Optional[date] = None,
) -> tuple:
    """
    Returns (all_active_supplements, taken_supplement_ids) for target_date.
    taken_supplement_ids is a set of supplement.id values that were logged.
    """
    target_date = target_date or date.today()

    all_supplements = (
        db.query(Supplement)
        .filter(Supplement.user_id == user_id, Supplement.is_active == True)
        .all()
    )
    taken_ids = {
        log.supplement_id
        for log in db.query(SupplementLog).filter(
            SupplementLog.user_id == user_id,
            SupplementLog.date == target_date,
        ).all()
    }
    return (all_supplements, taken_ids)
