from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from database.engine import get_db
from database.models import HevyExerciseSet, HevyWorkout

router = APIRouter(prefix="/api/hevy", tags=["hevy"])


@router.get("/exercises")
def list_exercises(db: Session = Depends(get_db)):
    """Return distinct exercise names that have at least one normal set with weight data."""
    rows = (
        db.query(HevyExerciseSet.exercise_name)
        .filter(HevyExerciseSet.set_type == "normal")
        .filter(HevyExerciseSet.weight_lbs.isnot(None))
        .filter(HevyExerciseSet.weight_lbs > 0)
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
        .filter(HevyExerciseSet.exercise_name == exercise_name)
        .filter(HevyExerciseSet.set_type == "normal")
        .filter(HevyExerciseSet.weight_lbs.isnot(None))
        .filter(HevyExerciseSet.weight_lbs > 0)
        .filter(HevyWorkout.start_time >= cutoff_dt)
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
