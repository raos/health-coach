import uuid
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List

from config import settings
from database.engine import get_db
from database.models import HevyExerciseSet, HevyWorkout, UserProfile
from dependencies import get_user_id

router = APIRouter(prefix="/api/hevy", tags=["hevy"])


@router.delete("/disconnect")
def disconnect_hevy(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile:
        profile.hevy_api_key = None
        db.commit()
    return {"status": "disconnected"}


@router.get("/exercises")
def list_exercises(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    """Return distinct exercise names that have at least one normal set with weight data."""
    rows = (
        db.query(HevyExerciseSet.exercise_name)
        .filter(
            HevyExerciseSet.user_id == user_id,
            HevyExerciseSet.set_type == "normal",
            HevyExerciseSet.weight_lbs.isnot(None),
            HevyExerciseSet.weight_lbs > 0,
        )
        .distinct()
        .order_by(HevyExerciseSet.exercise_name)
        .all()
    )
    return [r[0] for r in rows]


@router.get("/exercise-progress")
def get_exercise_progress(
    exercise_name: str = Query(...),
    weeks: int = Query(13),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    """
    Return per-week heaviest weight lifted for one exercise.
    Each point = Monday of that week, value = max weight_lbs across all normal sets that week.
    Also returns est_1rm (Epley) for the PR indicator in the UI.
    Marks a week as a PR if its max weight exceeds all prior weeks.
    """
    from datetime import date, timedelta, datetime as dt

    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    cutoff = this_monday - timedelta(weeks=weeks - 1)
    cutoff_dt = dt.combine(cutoff, dt.min.time())

    sets = (
        db.query(HevyExerciseSet, HevyWorkout.start_time)
        .join(HevyWorkout, HevyWorkout.id == HevyExerciseSet.workout_id)
        .filter(
            HevyExerciseSet.user_id == user_id,
            HevyExerciseSet.exercise_name == exercise_name,
            HevyExerciseSet.set_type == "normal",
            HevyExerciseSet.weight_lbs.isnot(None),
            HevyExerciseSet.weight_lbs > 0,
            HevyWorkout.start_time >= cutoff_dt,
        )
        .order_by(HevyWorkout.start_time)
        .all()
    )

    from collections import defaultdict
    # key = Monday ISO date of the week
    weeks_map: dict = defaultdict(lambda: {"max_weight_lbs": 0.0, "est_1rm": 0.0})

    for s, start_time in sets:
        d = start_time.date()
        monday = (d - timedelta(days=d.weekday())).isoformat()
        weight = s.weight_lbs or 0
        reps = s.reps or 1
        epley = weight * (1 + reps / 30.0)
        weeks_map[monday]["max_weight_lbs"] = max(weeks_map[monday]["max_weight_lbs"], weight)
        weeks_map[monday]["est_1rm"] = max(weeks_map[monday]["est_1rm"], epley)

    result = []
    running_max = 0.0
    for monday in sorted(weeks_map.keys()):
        v = weeks_map[monday]
        w = round(v["max_weight_lbs"], 1)
        est = round(v["est_1rm"], 1)
        is_pr = w > running_max
        if is_pr:
            running_max = w
        result.append({
            "date": monday,
            "max_weight_lbs": w,
            "est_1rm": est,
            "is_pr": is_pr,
        })

    return result


# ── Push routine to Hevy ───────────────────────────────────────────────────────

class PushExercise(BaseModel):
    name: str
    sets: int
    reps: str          # e.g. "8-12", "15-20"
    rest_seconds: int = 90
    coaching_note: str = ""


class PushRoutineRequest(BaseModel):
    title: str         # e.g. "Upper A — Horizontal Push + Vertical Pull"
    exercises: List[PushExercise]


def _normalize(text: str) -> str:
    """Lowercase, strip parentheses content, remove punctuation, collapse spaces."""
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"[^a-z0-9 ]", "", text.lower())
    return text.strip()


def _match_score(plan_name: str, template_title: str) -> float:
    """Return a 0–1 overlap score between plan exercise name and Hevy template title."""
    a_words = set(_normalize(plan_name).split())
    b_words = set(_normalize(template_title).split())
    if not a_words or not b_words:
        return 0.0
    common = a_words & b_words
    # Ignore very short words (articles, prepositions)
    common = {w for w in common if len(w) > 2}
    if not common:
        return 0.0
    return len(common) / max(len(a_words), len(b_words))


def _parse_reps(reps_str: str) -> int:
    """Parse '8-12' → 8, '15-20' → 15, '10' → 10, 'AMRAP' → 10."""
    m = re.match(r"(\d+)", reps_str.strip())
    return int(m.group(1)) if m else 10


@router.post("/push-routine")
def push_routine(
    payload: PushRoutineRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    """
    Create a routine in Hevy from a training plan day.
    Fuzzy-matches exercise names to Hevy exercise templates.
    Returns: { routine_id, matched: [...], unmatched: [...] }
    """
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    api_key = profile.hevy_api_key if profile else None
    if not api_key:
        raise HTTPException(status_code=503, detail="Hevy API key not configured. Add it in Settings.")

    from services.hevy_api_client import HevyAPIClient
    client = HevyAPIClient(api_key)

    # Fetch all exercise templates once
    templates = client.get_exercises(exclude_unused=False)

    hevy_exercises = []
    matched = []
    unmatched = []

    for ex in payload.exercises:
        # Find best-matching template
        best_score = 0.0
        best_template = None
        for tmpl in templates:
            score = _match_score(ex.name, tmpl.get("title", ""))
            if score > best_score:
                best_score = score
                best_template = tmpl

        MATCH_THRESHOLD = 0.4
        if best_template and best_score >= MATCH_THRESHOLD:
            reps = _parse_reps(ex.reps)
            hevy_exercises.append({
                "exercise_template_id": best_template["id"],
                "rest_seconds": ex.rest_seconds,
                "notes": ex.coaching_note[:500] if ex.coaching_note else "",
                "sets": [
                    {"type": "normal", "weight_kg": 0, "reps": reps}
                    for _ in range(ex.sets)
                ],
            })
            matched.append({
                "plan_name": ex.name,
                "hevy_name": best_template.get("title"),
                "score": round(best_score, 2),
            })
        else:
            unmatched.append(ex.name)

    if not hevy_exercises:
        raise HTTPException(
            status_code=422,
            detail=f"No exercises could be matched to Hevy templates. Unmatched: {unmatched}",
        )

    result = client.create_routine(title=payload.title, exercises=hevy_exercises)
    # Hevy may return {"routine": {...}}, {"routine": [...]}, a bare list, or {"id": ...}
    routine_id = None
    if isinstance(result, list):
        routine_id = result[0].get("id") if result else None
    elif isinstance(result, dict):
        inner = result.get("routine") or result
        if isinstance(inner, list):
            routine_id = inner[0].get("id") if inner else None
        elif isinstance(inner, dict):
            routine_id = inner.get("id")

    return {
        "routine_id": routine_id,
        "matched": matched,
        "unmatched": unmatched,
    }
