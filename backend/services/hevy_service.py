"""
Hevy service — calls the Hevy REST API directly via HevyAPIClient.
Requires HEVY_API_KEY in .env (get it from https://api.hevyapp.com/docs/#/)
"""
import json
from datetime import date, timedelta, datetime
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from database.models import HevyWorkout, HevyExerciseSet
from services.hevy_api_client import HevyAPIClient

_client: Optional[HevyAPIClient] = None


def is_configured() -> bool:
    return bool(settings.hevy_api_key)


def _get_client() -> HevyAPIClient:
    global _client
    if not is_configured():
        raise RuntimeError("HEVY_API_KEY not set in .env")
    if _client is None:
        _client = HevyAPIClient(settings.hevy_api_key)
    return _client


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _upsert_workout(db: Session, w: dict) -> bool:
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

    existing = db.query(HevyWorkout).filter(HevyWorkout.id == workout_id).first()
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
                workout_id=workout_id,
                exercise_name=ex_name,
                set_index=i,
                weight_lbs=weight_kg * 2.205 if weight_kg else None,
                reps=s.get("reps"),
                rpe=s.get("rpe"),
                set_type=s.get("set_type", "normal"),
            ))

    return is_new


def sync_workouts(db: Session, limit: int = 200) -> dict:
    """Fetch recent workouts via MCP and sync to DB. Returns counts of added/updated/deleted."""
    if not is_configured():
        return {"added": 0, "updated": 0, "deleted": 0}

    client = _get_client()
    cutoff_date = date.today() - timedelta(days=180)
    cutoff_str = cutoff_date.isoformat()
    workouts = client.get_workouts(limit=limit, start_date=cutoff_str)

    fetched_ids = {str(w.get("id", "")) for w in workouts if w.get("id")}

    # Delete local workouts (and their sets) within the 90-day window that
    # are no longer returned by Hevy — they were deleted by the user.
    cutoff_dt = datetime.combine(cutoff_date, datetime.min.time())
    stale = (
        db.query(HevyWorkout)
        .filter(HevyWorkout.start_time >= cutoff_dt)
        .filter(HevyWorkout.id.notin_(fetched_ids))
        .all()
    )
    deleted = len(stale)
    for row in stale:
        db.query(HevyExerciseSet).filter(HevyExerciseSet.workout_id == row.id).delete()
        db.delete(row)

    added = updated = 0
    for w in workouts:
        is_new = _upsert_workout(db, w)
        if is_new:
            added += 1
        else:
            updated += 1

    db.commit()
    return {"added": added, "updated": updated, "deleted": deleted}


def get_recent_workouts_summary(days: int = 14) -> str:
    """Return a text summary of recent workouts for AI context."""
    if not is_configured():
        return "Hevy not configured (add HEVY_API_KEY to .env)."
    try:
        client = _get_client()
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
