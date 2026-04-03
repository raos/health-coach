import uuid
from datetime import date, timedelta, datetime as dt
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.engine import get_db
from database.models import WeightLog, DexaScan, Vo2MaxLog, StravaActivity, HevyWorkout, UserProfile
from dependencies import get_user_id

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

TONAL_KEYWORDS = ["tonal", "free lift", "custom workout", "strength training on tonal"]
STRAVA_STRENGTH_TYPES = ["Workout", "WeightTraining"]


def _is_tonal(name: str) -> bool:
    return any(kw in name.lower() for kw in TONAL_KEYWORDS)


def _is_strava_strength(activity) -> bool:
    return activity.activity_type in STRAVA_STRENGTH_TYPES or _is_tonal(activity.name or "")


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    latest_weight = db.query(WeightLog).filter(WeightLog.user_id == user_id).order_by(desc(WeightLog.date)).first()
    latest_dexa = db.query(DexaScan).filter(DexaScan.user_id == user_id).order_by(desc(DexaScan.scan_date)).first()
    latest_vo2 = db.query(Vo2MaxLog).filter(Vo2MaxLog.user_id == user_id).order_by(desc(Vo2MaxLog.date)).first()
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

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
        "goal_date": str(profile.goal_date) if profile and profile.goal_date else "2026-12-31",
    }


@router.get("/weight-trend")
def get_weight_trend(
    days: int = 90,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    cutoff = date.today() - timedelta(days=days)
    entries = (
        db.query(WeightLog)
        .filter(WeightLog.user_id == user_id, WeightLog.date >= cutoff)
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
def get_activity_feed(
    limit: int = 10,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    strava = [
        a for a in (
            db.query(StravaActivity)
            .filter(
                StravaActivity.user_id == user_id,
                StravaActivity.activity_type.notin_(STRAVA_STRENGTH_TYPES),
            )
            .order_by(desc(StravaActivity.start_date))
            .limit(limit * 2)
            .all()
        )
        if not _is_tonal(a.name or "")
    ][:limit]

    hevy = (
        db.query(HevyWorkout)
        .filter(HevyWorkout.user_id == user_id)
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

    feed.sort(key=lambda x: x["date"], reverse=True)
    return feed[:limit]


@router.get("/workout-heatmap")
def get_workout_heatmap(
    weeks: int = 12,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    start_date = this_monday - timedelta(weeks=weeks - 1)
    start_dt = dt.combine(start_date, dt.min.time())

    hevy_list = db.query(HevyWorkout).filter(
        HevyWorkout.user_id == user_id,
        HevyWorkout.start_time >= start_dt,
    ).all()
    strava_list = db.query(StravaActivity).filter(
        StravaActivity.user_id == user_id,
        StravaActivity.start_date >= start_dt,
    ).all()

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


@router.get("/vo2-trend")
def get_vo2_trend(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    rows = db.query(Vo2MaxLog).filter(Vo2MaxLog.user_id == user_id).order_by(Vo2MaxLog.date).all()
    return [{"date": str(r.date), "vo2max": r.vo2max, "source": r.source} for r in rows]


@router.get("/goal-progress")
def get_goal_progress(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    latest_dexa = db.query(DexaScan).filter(DexaScan.user_id == user_id).order_by(desc(DexaScan.scan_date)).first()
    latest_vo2 = db.query(Vo2MaxLog).filter(Vo2MaxLog.user_id == user_id).order_by(desc(Vo2MaxLog.date)).first()

    baseline_bf = latest_dexa.body_fat_pct if latest_dexa else 28.4
    baseline_vo2 = 45.0
    bf_goal = profile.bf_goal_pct if profile and profile.bf_goal_pct else 18.0
    vo2_goal = profile.vo2max_goal if profile and profile.vo2max_goal else 50.0

    bf_current = latest_dexa.body_fat_pct if latest_dexa else baseline_bf
    vo2_current = latest_vo2.vo2max if latest_vo2 else baseline_vo2

    bf_total_gap = baseline_bf - bf_goal
    bf_closed = baseline_bf - bf_current
    bf_pct_complete = max(0, min(100, (bf_closed / bf_total_gap * 100) if bf_total_gap > 0 else 0))

    vo2_total_gap = vo2_goal - baseline_vo2
    vo2_gained = vo2_current - baseline_vo2
    vo2_pct_complete = max(0, min(100, (vo2_gained / vo2_total_gap * 100) if vo2_total_gap > 0 else 0))

    current_weight = db.query(WeightLog).filter(WeightLog.user_id == user_id).order_by(desc(WeightLog.date)).first()
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
