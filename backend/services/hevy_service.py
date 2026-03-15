"""
Hevy service — uses the @vreippainen/hevy-mcp-server MCP server.
Requires HEVY_API_KEY in .env (get it from https://api.hevyapp.com/docs/#/)
"""
import json
from datetime import date, timedelta, datetime
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from database.models import HevyWorkout, HevyExerciseSet
from services.hevy_mcp_client import HevyMCPClient

_client: Optional[HevyMCPClient] = None


def is_configured() -> bool:
    return bool(settings.hevy_api_key)


def _get_client() -> HevyMCPClient:
    global _client
    if not is_configured():
        raise RuntimeError("HEVY_API_KEY not set in .env")
    if _client is None:
        _client = HevyMCPClient(settings.hevy_api_key)
    return _client


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def sync_workouts(db: Session, limit: int = 30) -> int:
    """Fetch recent workouts via MCP and sync to DB. Returns count of new records."""
    if not is_configured():
        return 0

    client = _get_client()
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    workouts = client.get_workouts(limit=limit, start_date=cutoff)

    count = 0
    for w in workouts:
        workout_id = str(w.get("id", ""))
        if not workout_id:
            continue

        if db.query(HevyWorkout).filter(HevyWorkout.id == workout_id).first():
            continue

        start_time = _parse_dt(w.get("start_time") or w.get("created_at"))
        end_time = _parse_dt(w.get("end_time"))
        if not start_time:
            continue

        exercises = w.get("exercises", [])
        total_volume = 0.0
        for ex in exercises:
            for s in ex.get("sets", []):
                weight = s.get("weight_kg", 0) or 0
                reps = s.get("reps", 0) or 0
                total_volume += weight * 2.205 * reps

        workout_obj = HevyWorkout(
            id=workout_id,
            title=w.get("title", "Hevy Workout"),
            start_time=start_time,
            end_time=end_time,
            duration_s=w.get("duration"),
            volume_lbs=total_volume if total_volume > 0 else None,
            raw_json=json.dumps(w),
        )
        db.add(workout_obj)

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

        count += 1

    db.commit()
    return count


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
