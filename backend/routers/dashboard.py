from datetime import date, timedelta, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.engine import get_db
from database.models import WeightLog, DexaScan, Vo2MaxLog, StravaActivity, HevyWorkout, UserProfile

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

TONAL_KEYWORDS = ["tonal", "free lift", "custom workout", "strength training on tonal"]

# Strava activity types that are strength/weight training — sourced from Hevy instead
STRAVA_STRENGTH_TYPES = ["Workout", "WeightTraining"]


def _is_tonal(name: str) -> bool:
    return any(kw in name.lower() for kw in TONAL_KEYWORDS)


def _is_strava_strength(activity) -> bool:
    """True if this Strava activity is a strength/weight-training session (already in Hevy)."""
    return activity.activity_type in STRAVA_STRENGTH_TYPES or _is_tonal(activity.name or "")


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    latest_weight = db.query(WeightLog).order_by(desc(WeightLog.date)).first()
    latest_dexa = db.query(DexaScan).order_by(desc(DexaScan.scan_date)).first()
    latest_vo2 = db.query(Vo2MaxLog).order_by(desc(Vo2MaxLog.date)).first()
    profile = db.query(UserProfile).first()

    return {
        "latest_weight": {
            "id": latest_weight.id,
            "date": str(latest_weight.date),
            "weight_lbs": latest_weight.weight_lbs,
            "source": latest_weight.source,
            "created_at": latest_weight.created_at.isoformat(),
        } if latest_weight else None,
        "latest_dexa": {
            "id": latest_dexa.id,
            "scan_date": str(latest_dexa.scan_date),
            "total_weight_lbs": latest_dexa.total_weight_lbs,
            "body_fat_pct": latest_dexa.body_fat_pct,
            "fat_mass_lbs": latest_dexa.fat_mass_lbs,
            "lean_mass_lbs": latest_dexa.lean_mass_lbs,
            "visceral_fat_lbs": latest_dexa.visceral_fat_lbs,
            "ag_ratio": latest_dexa.ag_ratio,
        } if latest_dexa else None,
        "latest_vo2max": {
            "id": latest_vo2.id,
            "date": str(latest_vo2.date),
            "vo2max": latest_vo2.vo2max,
            "source": latest_vo2.source,
        } if latest_vo2 else None,
        "goal_bf_pct": profile.bf_goal_pct if profile else 18.0,
        "goal_vo2max": profile.vo2max_goal if profile else 50.0,
        "goal_date": str(profile.goal_date) if profile else "2026-12-31",
    }


@router.get("/weight-trend")
def get_weight_trend(days: int = 90, db: Session = Depends(get_db)):
    cutoff = date.today() - timedelta(days=days)
    entries = (
        db.query(WeightLog)
        .filter(WeightLog.date >= cutoff)
        .order_by(WeightLog.date)
        .all()
    )
    return [
        {
            "id": e.id,
            "date": str(e.date),
            "weight_lbs": e.weight_lbs,
            "notes": e.notes,
            "source": e.source,
            "created_at": e.created_at.isoformat(),
        }
        for e in entries
    ]


@router.get("/activity-feed")
def get_activity_feed(limit: int = 10, db: Session = Depends(get_db)):
    strava = [
        a for a in (
            db.query(StravaActivity)
            .filter(StravaActivity.activity_type.notin_(STRAVA_STRENGTH_TYPES))
            .order_by(desc(StravaActivity.start_date))
            .limit(limit * 2)
            .all()
        )
        if not _is_tonal(a.name or "")
    ][:limit]
    hevy = (
        db.query(HevyWorkout)
        .order_by(desc(HevyWorkout.start_time))
        .limit(limit)
        .all()
    )

    feed = []
    for a in strava:
        feed.append({
            "id": f"strava-{a.id}",
            "type": "strava",
            "name": a.name,
            "activity_type": a.activity_type,
            "date": a.start_date.isoformat(),
            "distance_m": a.distance_m,
            "moving_time_s": a.moving_time_s,
            "average_hr": a.average_hr,
            "is_tonal": _is_tonal(a.name),
        })
    for w in hevy:
        feed.append({
            "id": f"hevy-{w.id}",
            "type": "hevy",
            "name": w.title or "Hevy Workout",
            "activity_type": "Strength",
            "date": w.start_time.isoformat(),
            "volume_lbs": w.volume_lbs,
            "moving_time_s": w.duration_s,
            "is_tonal": True,
        })

    # Sort merged feed by date descending
    feed.sort(key=lambda x: x["date"], reverse=True)
    return feed[:limit]


@router.get("/workout-heatmap")
def get_workout_heatmap(weeks: int = 12, db: Session = Depends(get_db)):
    """Return per-day workout data for the last N weeks for the consistency heatmap."""
    from datetime import datetime as dt
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    start_date = this_monday - timedelta(weeks=weeks - 1)
    start_dt = dt.combine(start_date, dt.min.time())

    hevy_list = db.query(HevyWorkout).filter(HevyWorkout.start_time >= start_dt).all()
    # Include ALL Strava activities in the heatmap (no dedup needed — we just need to know
    # whether a workout happened on a given day; deduplication only applies to the feed).
    strava_list = (
        db.query(StravaActivity)
        .filter(StravaActivity.start_date >= start_dt)
        .all()
    )

    # Track which days already have a Hevy entry so we don't double-count strength sessions
    # that are logged in both Hevy and Strava.
    hevy_days: set = set()
    day_map: dict = {}

    for w in hevy_list:
        d = w.start_time.date().isoformat()
        hevy_days.add(d)
        entry = day_map.setdefault(d, {"hevy_volume_lbs": 0.0, "cardio_minutes": 0.0, "total_minutes": 0.0, "types": set(), "count": 0})
        entry["hevy_volume_lbs"] += w.volume_lbs or 0
        entry["total_minutes"] += (w.duration_s or 0) / 60
        entry["types"].add("strength")
        entry["count"] += 1

    for a in strava_list:
        d = a.start_date.date().isoformat()
        is_strength = _is_strava_strength(a)
        # Skip Strava strength activities on days already covered by Hevy to avoid double-counting
        if is_strength and d in hevy_days:
            continue
        entry = day_map.setdefault(d, {"hevy_volume_lbs": 0.0, "cardio_minutes": 0.0, "total_minutes": 0.0, "types": set(), "count": 0})
        mins = (a.moving_time_s or 0) / 60
        entry["cardio_minutes"] += mins
        entry["total_minutes"] += mins
        entry["types"].add("strength" if is_strength else "cardio")
        entry["count"] += 1

    return [
        {
            "date": d,
            "count": v["count"],
            "hevy_volume_lbs": round(v["hevy_volume_lbs"], 1),
            "cardio_minutes": round(v["cardio_minutes"], 1),
            "total_minutes": round(v["total_minutes"], 1),
            "types": sorted(v["types"]),
        }
        for d, v in sorted(day_map.items())
    ]


@router.get("/goal-progress")
def get_goal_progress(db: Session = Depends(get_db)):
    profile = db.query(UserProfile).first()
    latest_dexa = db.query(DexaScan).order_by(desc(DexaScan.scan_date)).first()
    latest_vo2 = db.query(Vo2MaxLog).order_by(desc(Vo2MaxLog.date)).first()

    baseline_bf = 28.4
    baseline_vo2 = 45.0
    bf_goal = profile.bf_goal_pct if profile else 18.0
    vo2_goal = profile.vo2max_goal if profile else 50.0

    bf_current = latest_dexa.body_fat_pct if latest_dexa else baseline_bf
    vo2_current = latest_vo2.vo2max if latest_vo2 else baseline_vo2

    # Progress: how much of the gap from baseline to goal has been closed
    bf_total_gap = baseline_bf - bf_goal
    bf_closed = baseline_bf - bf_current
    bf_pct_complete = max(0, min(100, (bf_closed / bf_total_gap * 100) if bf_total_gap > 0 else 0))

    vo2_total_gap = vo2_goal - baseline_vo2
    vo2_gained = vo2_current - baseline_vo2
    vo2_pct_complete = max(0, min(100, (vo2_gained / vo2_total_gap * 100) if vo2_total_gap > 0 else 0))

    # Lbs of fat still to lose
    current_weight = (
        db.query(WeightLog).order_by(desc(WeightLog.date)).first()
    )
    weight = current_weight.weight_lbs if current_weight else (latest_dexa.total_weight_lbs if latest_dexa else 181.5)
    target_fat_mass = weight * (bf_goal / 100)
    current_fat_mass = weight * (bf_current / 100)
    bf_lbs_to_lose = max(0, current_fat_mass - target_fat_mass)

    return {
        "bf_current": bf_current,
        "bf_goal": bf_goal,
        "bf_pct_complete": round(bf_pct_complete, 1),
        "bf_lbs_to_lose": round(bf_lbs_to_lose, 1),
        "vo2_current": vo2_current,
        "vo2_goal": vo2_goal,
        "vo2_pct_complete": round(vo2_pct_complete, 1),
    }


def _linreg(dates: list, values: list):
    """Simple linear regression. Returns (slope per day, intercept) or (None, None)."""
    if len(dates) < 2:
        return None, None
    x = [(d - dates[0]).days for d in dates]
    n = len(x)
    xm = sum(x) / n
    ym = sum(values) / n
    denom = sum((xi - xm) ** 2 for xi in x)
    if denom == 0:
        return None, None
    slope = sum((x[i] - xm) * (values[i] - ym) for i in range(n)) / denom
    intercept = ym - slope * xm
    return slope, intercept


def _projection_status(projected_date, goal_date):
    if projected_date is None:
        return "insufficient_data"
    diff_days = (projected_date - goal_date).days
    diff_weeks = diff_days / 7
    if diff_weeks < -2:
        return "ahead"
    elif diff_weeks <= 2:
        return "on_track"
    else:
        return "behind"


@router.get("/goal-projection")
def goal_projection(db: Session = Depends(get_db)):
    today = date.today()
    profile = db.query(UserProfile).first()
    goal_bf = profile.bf_goal_pct if profile else 18.0
    goal_vo2 = profile.vo2max_goal if profile else 50.0
    goal_date = profile.goal_date if profile else date(2026, 12, 31)

    # ── Latest DEXA ────────────────────────────────────────────────────────────
    latest_dexa = db.query(DexaScan).order_by(desc(DexaScan.scan_date)).first()
    lean_mass = latest_dexa.lean_mass_lbs if latest_dexa else 123.9
    dexa_bf = latest_dexa.body_fat_pct if latest_dexa else 28.4
    dexa_date = latest_dexa.scan_date if latest_dexa else date(2026, 3, 13)

    # goal weight = lean_mass / (1 - goal_bf/100)
    goal_weight = lean_mass / (1 - goal_bf / 100)

    # ── BF% calibration factor ────────────────────────────────────────────────
    calibration_factor = None
    calibration_date = None
    if latest_dexa:
        scale_entry = (
            db.query(WeightLog)
            .filter(WeightLog.date == latest_dexa.scan_date, WeightLog.body_fat_pct.isnot(None))
            .first()
        )
        if scale_entry and scale_entry.body_fat_pct and scale_entry.body_fat_pct > 0:
            calibration_factor = round(dexa_bf / scale_entry.body_fat_pct, 3)
            calibration_date = str(latest_dexa.scan_date)

    # ── Weight regression (last 30 days) ─────────────────────────────────────
    cutoff_30 = today - timedelta(days=30)
    weight_rows = (
        db.query(WeightLog)
        .filter(WeightLog.date >= cutoff_30)
        .order_by(WeightLog.date)
        .all()
    )
    w_dates = [r.date for r in weight_rows]
    w_values = [r.weight_lbs for r in weight_rows]
    current_weight = w_values[-1] if w_values else (latest_dexa.total_weight_lbs if latest_dexa else 181.5)

    w_slope, w_intercept = _linreg(w_dates, w_values)
    w_projected_date = None
    if w_slope is not None and w_slope < 0:
        days_to_goal = (goal_weight - w_intercept) / w_slope
        w_projected_date = w_dates[0] + timedelta(days=days_to_goal)
    elif w_slope is not None and w_slope >= 0:
        w_projected_date = None  # no_trend

    w_weeks_diff = round((w_projected_date - goal_date).days / 7) if w_projected_date else None
    w_status = (
        _projection_status(w_projected_date, goal_date)
        if w_slope is not None
        else ("no_trend" if w_slope == 0 else "insufficient_data")
    )
    if w_slope is not None and w_slope >= 0:
        w_status = "no_trend"

    # ── BF% projection (weight-derived via lean mass) ─────────────────────────
    current_bf = round((current_weight - lean_mass) / current_weight * 100, 1) if current_weight else dexa_bf
    bf_projected_date = w_projected_date  # same as weight since goal weight = goal BF%

    bf_weeks_diff = round((bf_projected_date - goal_date).days / 7) if bf_projected_date else None
    bf_status = w_status  # correlated with weight projection

    # ── VO2 max regression ────────────────────────────────────────────────────
    vo2_rows = db.query(Vo2MaxLog).order_by(Vo2MaxLog.date).all()
    v_dates = [r.date for r in vo2_rows]
    v_values = [r.vo2max for r in vo2_rows]
    current_vo2 = v_values[-1] if v_values else 45.0

    v_slope, v_intercept = _linreg(v_dates, v_values)
    v_projected_date = None
    if v_slope is not None and v_slope > 0:
        days_to_vo2_goal = (goal_vo2 - v_intercept) / v_slope
        v_projected_date = v_dates[0] + timedelta(days=days_to_vo2_goal)

    v_weeks_diff = round((v_projected_date - goal_date).days / 7) if v_projected_date else None
    v_status = (
        _projection_status(v_projected_date, goal_date)
        if (v_slope is not None and v_slope > 0)
        else ("insufficient_data" if v_slope is None else "no_trend")
    )

    # ── Chart data ────────────────────────────────────────────────────────────
    # actual: last 90 days of weight logs + derived BF%
    cutoff_90 = today - timedelta(days=90)
    chart_rows = (
        db.query(WeightLog)
        .filter(WeightLog.date >= cutoff_90)
        .order_by(WeightLog.date)
        .all()
    )
    actual_points = [
        {
            "date": str(r.date),
            "weight": r.weight_lbs,
            "bf_pct": round((r.weight_lbs - lean_mass) / r.weight_lbs * 100, 1),
        }
        for r in chart_rows
    ]

    # required: straight line from today to goal_date at goal_weight
    required_points = [
        {"date": str(today), "weight": round(current_weight, 1)},
        {"date": str(goal_date), "weight": round(goal_weight, 1)},
    ]

    # projected: from today to projected_date at goal_weight (if calculable)
    projected_points = []
    if w_projected_date and w_slope is not None and w_slope < 0:
        projected_points = [
            {"date": str(today), "weight": round(current_weight, 1)},
            {"date": str(w_projected_date.date() if isinstance(w_projected_date, datetime) else w_projected_date), "weight": round(goal_weight, 1)},
        ]

    return {
        "goal_date": str(goal_date),
        "days_remaining": (goal_date - today).days,
        "weight": {
            "current_lbs": round(current_weight, 1),
            "goal_lbs": round(goal_weight, 1),
            "slope_lbs_per_day": round(w_slope, 4) if w_slope is not None else None,
            "projected_goal_date": str(w_projected_date.date() if isinstance(w_projected_date, datetime) else w_projected_date) if w_projected_date else None,
            "weeks_diff": w_weeks_diff,
            "status": w_status,
            "data_points": len(w_dates),
        },
        "body_fat": {
            "current_pct": current_bf,
            "goal_pct": goal_bf,
            "lean_mass_lbs": round(lean_mass, 1),
            "dexa_date": str(dexa_date),
            "projected_goal_date": str(bf_projected_date.date() if isinstance(bf_projected_date, datetime) else bf_projected_date) if bf_projected_date else None,
            "weeks_diff": bf_weeks_diff,
            "status": bf_status,
            "calibration_factor": calibration_factor,
            "calibration_date": calibration_date,
        },
        "vo2max": {
            "current": round(current_vo2, 1),
            "goal": goal_vo2,
            "slope_per_day": round(v_slope, 6) if v_slope is not None else None,
            "projected_goal_date": str(v_projected_date.date() if isinstance(v_projected_date, datetime) else v_projected_date) if v_projected_date else None,
            "weeks_diff": v_weeks_diff,
            "status": v_status,
            "data_points": len(v_dates),
        },
        "chart": {
            "actual": actual_points,
            "required": required_points,
            "projected": projected_points,
        },
    }
