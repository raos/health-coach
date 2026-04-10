from datetime import date, timedelta
from typing import Optional
import uuid

from sqlalchemy.orm import Session


def _linear_regression(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Ordinary least-squares. Returns (slope, intercept) for y = slope*x + intercept."""
    n = len(points)
    sx = sum(x for x, _ in points)
    sy = sum(y for _, y in points)
    sxx = sum(x * x for x, _ in points)
    sxy = sum(x * y for x, y in points)
    denom = n * sxx - sx * sx
    if denom == 0:
        return 0.0, sy / n
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return slope, intercept


def _date_to_x(d: date) -> float:
    """Convert date to a float (days since 2000-01-01) for regression."""
    return float((d - date(2000, 1, 1)).days)


def _compute_trajectory(
    logs: list[tuple[date, float]],
    goal_value: float,
    goal_date: date,
    lookback_weeks: int = 8,
) -> Optional[dict]:
    """
    Compute actual / required / projected trajectory for one metric.

    Args:
        logs: List of (date, value) tuples, unsorted.
        goal_value: Target value to reach by goal_date.
        goal_date: Target date.
        lookback_weeks: How many weeks of recent data to use for regression.

    Returns None if logs is empty. Otherwise returns:
        {
            actual: [{"date": "YYYY-MM-DD", "value": float}, ...],
            required: [two-point straight line from first log to goal],
            projected: [two-point projection from today to goal_date] or None,
            current: float,
            goal: float,
            weeks_delta: int (positive = ahead, negative = behind),
        }
    """
    if not logs:
        return None

    today = date.today()
    logs_sorted = sorted(logs, key=lambda t: t[0])
    first_date, first_value = logs_sorted[0]
    _current_date, current_value = logs_sorted[-1]

    actual = [{"date": str(d), "value": round(v, 2)} for d, v in logs_sorted]

    required = [
        {"date": str(first_date), "value": round(first_value, 2)},
        {"date": str(goal_date), "value": round(goal_value, 2)},
    ]

    # Regression on recent data
    cutoff = today - timedelta(weeks=lookback_weeks)
    recent = [(d, v) for d, v in logs_sorted if d >= cutoff]
    projected = None
    weeks_delta = 0

    if len(recent) >= 3:
        points = [(_date_to_x(d), v) for d, v in recent]
        slope, intercept = _linear_regression(points)

        today_x = _date_to_x(today)
        goal_x = _date_to_x(goal_date)
        projected_today = slope * today_x + intercept
        projected_at_goal = slope * goal_x + intercept

        projected = [
            {"date": str(today), "value": round(projected_today, 2)},
            {"date": str(goal_date), "value": round(projected_at_goal, 2)},
        ]

        # weeks_delta: solve slope*x + intercept = goal_value for x
        if abs(slope) > 1e-9:
            crossing_x = (goal_value - intercept) / slope
            crossing_date = date(2000, 1, 1) + timedelta(days=int(crossing_x))
            weeks_delta = round((goal_date - crossing_date).days / 7)

    return {
        "actual": actual,
        "required": required,
        "projected": projected,
        "current": round(current_value, 2),
        "goal": round(goal_value, 2),
        "weeks_delta": weeks_delta,
    }


def get_goal_projection(db: Session, user_id: uuid.UUID) -> dict:
    """Return projection data for weight and BF% toward the user's goal date."""
    from database.models import WeightLog, UserProfile

    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile or not profile.goal_date:
        return {"goal_date": None, "weight": None, "bf_pct": None}

    goal_date = profile.goal_date

    weight_result = None
    if profile.weight_goal_lbs:
        weight_logs = (
            db.query(WeightLog)
            .filter(WeightLog.user_id == user_id)
            .order_by(WeightLog.date)
            .all()
        )
        weight_result = _compute_trajectory(
            [(w.date, w.weight_lbs) for w in weight_logs],
            profile.weight_goal_lbs,
            goal_date,
        )

    bf_result = None
    if profile.bf_goal_pct:
        bf_logs = (
            db.query(WeightLog)
            .filter(WeightLog.user_id == user_id, WeightLog.body_fat_pct.isnot(None))
            .order_by(WeightLog.date)
            .all()
        )
        bf_result = _compute_trajectory(
            [(w.date, w.body_fat_pct) for w in bf_logs],
            profile.bf_goal_pct,
            goal_date,
        )

    return {
        "goal_date": str(goal_date),
        "weight": weight_result,
        "bf_pct": bf_result,
    }
