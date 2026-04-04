"""
Hevy service — calls the Hevy REST API directly via HevyAPIClient.
API key is stored per-user in UserProfile.hevy_api_key.
"""
import json
from datetime import date, timedelta, datetime
from typing import Optional

from sqlalchemy.orm import Session

from database.models import HevyWorkout, HevyExerciseSet
from services.hevy_api_client import HevyAPIClient


def is_configured(api_key: Optional[str] = None) -> bool:
    return bool(api_key)


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _upsert_workout(db: Session, w: dict, user_id=None) -> bool:
    """Insert or replace a single Hevy workout and its sets. Returns True if new."""
    workout_id = str(w.get("id", ""))
    if not workout_id:
        return False

    start_time = _parse_dt(w.get("start_time") or w.get("created_at"))
    if not start_time:
        return False

    end_time = _parse_dt(w.get("end_time"))
    exercises = w.get("exercises", [])
    total_volume = sum(
        (s.get("weight_kg", 0) or 0) * 2.205 * (s.get("reps", 0) or 0)
        for ex in exercises
        for s in ex.get("sets", [])
    )

    q = db.query(HevyWorkout).filter(HevyWorkout.id == workout_id)
    if user_id is not None:
        q = q.filter(HevyWorkout.user_id == user_id)
    existing = q.first()
    is_new = existing is None

    if existing:
        existing.title = w.get("title", "Hevy Workout")
        existing.start_time = start_time
        existing.end_time = end_time
        existing.duration_s = w.get("duration")
        existing.volume_lbs = total_volume if total_volume > 0 else None
        existing.raw_json = json.dumps(w)
        # Replace sets
        db.query(HevyExerciseSet).filter(HevyExerciseSet.workout_id == workout_id).delete()
    else:
        db.add(HevyWorkout(
            id=workout_id,
            user_id=user_id,
            title=w.get("title", "Hevy Workout"),
            start_time=start_time,
            end_time=end_time,
            duration_s=w.get("duration"),
            volume_lbs=total_volume if total_volume > 0 else None,
            raw_json=json.dumps(w),
        ))

    for ex in exercises:
        ex_name = ex.get("title") or ex.get("exercise_template", {}).get("title", "Unknown")
        for i, s in enumerate(ex.get("sets", [])):
            weight_kg = s.get("weight_kg", 0) or 0
            db.add(HevyExerciseSet(
                user_id=user_id,
                workout_id=workout_id,
                exercise_name=ex_name,
                set_index=i,
                weight_lbs=weight_kg * 2.205 if weight_kg else None,
                reps=s.get("reps"),
                rpe=s.get("rpe"),
                set_type=s.get("set_type", "normal"),
            ))

    return is_new


def sync_workouts(db: Session, user_id=None, api_key: Optional[str] = None, limit: int = 200) -> dict:
    """Fetch recent workouts via Hevy REST API and sync to DB. Returns counts of added/updated/deleted."""
    if not api_key:
        return {"added": 0, "updated": 0, "deleted": 0}

    client = HevyAPIClient(api_key)
    cutoff_date = date.today() - timedelta(days=180)
    cutoff_str = cutoff_date.isoformat()
    workouts = client.get_workouts(limit=limit, start_date=cutoff_str)

    fetched_ids = {str(w.get("id", "")) for w in workouts if w.get("id")}

    # Delete local workouts within the window that are no longer in Hevy
    cutoff_dt = datetime.combine(cutoff_date, datetime.min.time())
    stale_q = (
        db.query(HevyWorkout)
        .filter(HevyWorkout.start_time >= cutoff_dt)
        .filter(HevyWorkout.id.notin_(fetched_ids))
    )
    if user_id is not None:
        stale_q = stale_q.filter(HevyWorkout.user_id == user_id)
    stale = stale_q.all()
    deleted = len(stale)
    for row in stale:
        db.query(HevyExerciseSet).filter(HevyExerciseSet.workout_id == row.id).delete()
        db.delete(row)

    added = updated = 0
    for w in workouts:
        is_new = _upsert_workout(db, w, user_id=user_id)
        if is_new:
            added += 1
        else:
            updated += 1

    db.commit()
    return {"added": added, "updated": updated, "deleted": deleted}


def get_recent_workouts_summary(days: int = 14, api_key: Optional[str] = None) -> str:
    """Return a text summary of recent workouts for AI context."""
    if not is_configured(api_key):
        return "Hevy not configured. Add your API key in Settings."
    try:
        client = HevyAPIClient(api_key)
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        workouts = client.get_workouts(limit=10, start_date=cutoff)
        if not workouts:
            return "No Hevy workouts found in the last 14 days."
        lines = []
        for w in workouts:
            title = w.get("title", "Workout")
            start = (w.get("start_time") or "")[:10]
            volume = w.get("volume", {})
            vol_str = ""
            if isinstance(volume, dict) and volume.get("total_kg"):
                vol_str = f" — {volume['total_kg'] * 2.205:.0f} lbs volume"
            lines.append(f"  - {start}: {title}{vol_str}")
        return "\n".join(lines)
    except Exception as e:
        return f"Hevy data unavailable: {e}"
