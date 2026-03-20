import hashlib
import json
from datetime import date, timedelta
from typing import Optional, AsyncGenerator

import anthropic
from sqlalchemy.orm import Session
from sqlalchemy import desc

from config import settings
from database.models import (
    WeightLog, DexaScan, Vo2MaxLog, StravaActivity, HevyWorkout,
    HevyExerciseSet, UserProfile, TrainingPlan
)
from prompts.coach_system import COACH_SYSTEM_PROMPT, COACH_CHAT_SYSTEM
from prompts.nutrition_system import NUTRITION_SYSTEM_PROMPT
from prompts.health_advisor_system import HEALTH_ADVISOR_SYSTEM_PROMPT


def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _build_current_stats(db: Session) -> str:
    latest_dexa = db.query(DexaScan).order_by(desc(DexaScan.scan_date)).first()
    latest_weight = db.query(WeightLog).order_by(desc(WeightLog.date)).first()
    latest_vo2 = db.query(Vo2MaxLog).order_by(desc(Vo2MaxLog.date)).first()
    profile = db.query(UserProfile).first()

    bf = latest_dexa.body_fat_pct if latest_dexa else 28.4
    lean = latest_dexa.lean_mass_lbs if latest_dexa else 123.9
    weight = latest_weight.weight_lbs if latest_weight else (latest_dexa.total_weight_lbs if latest_dexa else 181.5)
    vo2 = latest_vo2.vo2max if latest_vo2 else 45.0
    dexa_date = str(latest_dexa.scan_date) if latest_dexa else "2026-03-13"

    return f"""- Weight: {weight} lbs (as of {str(latest_weight.date) if latest_weight else "unknown"})
- Body fat: {bf}% (DEXA as of {dexa_date})
- Lean mass: {lean} lbs
- VO2 Max: {vo2} (goal: {profile.vo2max_goal if profile else 50.0}+ by {str(profile.goal_date) if profile else "2026-12-31"})
- Body fat goal: {profile.bf_goal_pct if profile else 18.0}% by {str(profile.goal_date) if profile else "2026-12-31"}
- Age: 46, training exclusively on Tonal (cable-based)"""


def _build_recent_training(db: Session) -> str:
    cutoff = date.today() - timedelta(days=14)

    strava = (
        db.query(StravaActivity)
        .filter(StravaActivity.start_date >= cutoff.isoformat())
        .filter(StravaActivity.activity_type.notin_(["Workout", "WeightTraining"]))
        .order_by(desc(StravaActivity.start_date))
        .limit(10)
        .all()
    )
    hevy = (
        db.query(HevyWorkout)
        .filter(HevyWorkout.start_time >= cutoff.isoformat())
        .order_by(desc(HevyWorkout.start_time))
        .limit(10)
        .all()
    )

    lines = []
    for a in strava:
        dist = f"{a.distance_m / 1609.34:.2f} mi" if a.distance_m else ""
        hr = f"avg HR {a.average_hr} bpm" if a.average_hr else ""
        lines.append(f"  - [Strava] {str(a.start_date)[:10]} {a.activity_type}: {a.name} {dist} {hr}".strip())
    for w in hevy:
        vol = f"{w.volume_lbs:.0f} lbs volume" if w.volume_lbs else ""
        lines.append(f"  - [Hevy/Tonal] {str(w.start_time)[:10]}: {w.title or 'Workout'} {vol}".strip())

    if not lines:
        return "No recent training data available yet. Sync Strava and Hevy in the Coach section."
    return "\n".join(lines)


def build_context_hash(db: Session) -> str:
    stats = _build_current_stats(db)
    training = _build_recent_training(db)
    return hashlib.md5(f"{stats}{training}".encode()).hexdigest()


def _build_weekly_schedule(strength_days: int, cardio_days: int, rest_days: int) -> list[dict]:
    """
    Build a 7-day schedule assigning session types to Mon–Sun.
    Strength sessions alternate upper/lower and vary A/B for repeated sessions.
    Cardio days are interleaved between strength for recovery. Rest on Sunday by default.
    """
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    # Build strength session labels: alternate upper/lower, A then B
    upper_count = (strength_days + 1) // 2  # ceil(n/2)
    lower_count = strength_days // 2         # floor(n/2)
    upper_labels = [f"Upper {'ABCDE'[i]}" for i in range(upper_count)]
    lower_labels = [f"Lower {'ABCDE'[i]}" for i in range(lower_count)]

    # Interleave upper and lower: Upper A, Lower A, Upper B, Lower B, ...
    strength_sequence = []
    for i in range(max(upper_count, lower_count)):
        if i < upper_count:
            strength_sequence.append(upper_labels[i])
        if i < lower_count:
            strength_sequence.append(lower_labels[i])
    strength_sequence = strength_sequence[:strength_days]

    # Assign sessions to days: spread strength days, fill gaps with cardio/rest
    # Strategy: place a cardio day after every 2 consecutive strength days when possible
    schedule = []
    si = 0   # strength index
    ci = 0   # cardio count used
    ri = 0   # rest count used

    for day_name in days_of_week:
        if si < strength_days:
            # After every pair of strength days, try to insert cardio if available
            if si > 0 and si % 2 == 0 and ci < cardio_days:
                schedule.append({"day": day_name, "type": "Cardio"})
                ci += 1
            else:
                schedule.append({"day": day_name, "type": strength_sequence[si]})
                si += 1
        elif ci < cardio_days:
            schedule.append({"day": day_name, "type": "Cardio"})
            ci += 1
        elif ri < rest_days:
            schedule.append({"day": day_name, "type": "Rest"})
            ri += 1

    return schedule


def _device_instruction(training_device: str) -> str:
    if training_device == "gym":
        return "Exercises use standard gym equipment: barbells, dumbbells, cables, machines, and bodyweight."
    elif training_device == "bodyweight":
        return "ALL exercises must be bodyweight only — no equipment required."
    else:  # default: tonal
        return "ALL exercises must be Tonal-compatible (cable-based only, 0-200 lb resistance). No free barbells, no dumbbells."


def _measurement_instruction(measurement_system: str) -> str:
    if measurement_system == "metric":
        return "Always respond using metric units (kg, cm, km). Convert all measurements to metric."
    else:  # default: imperial
        return "Always respond using imperial units (lbs, inches, miles)."


def generate_training_plan(
    db: Session,
    strength_days: int = 4,
    cardio_days: int = 2,
    rest_days: int = 1,
) -> dict:
    client = _get_client()
    current_stats = _build_current_stats(db)
    recent_training = _build_recent_training(db)
    profile = db.query(UserProfile).first()
    training_device = (profile.training_device if profile and profile.training_device else "tonal")
    measurement_system = (profile.measurement_system if profile and profile.measurement_system else "imperial")

    device_note = _device_instruction(training_device)
    measurement_note = _measurement_instruction(measurement_system)

    system = COACH_SYSTEM_PROMPT.format(
        current_stats=current_stats,
        recent_training=recent_training,
    ) + f"\n\n## Equipment Constraint\n{device_note}\n\n## Units\n{measurement_note}"

    today = date.today()
    days_to_monday = (7 - today.weekday()) % 7 or 7
    next_monday = today + timedelta(days=days_to_monday)

    schedule = _build_weekly_schedule(strength_days, cardio_days, rest_days)
    schedule_desc = "\n".join(
        f"  - {s['day']}: {s['type']}" for s in schedule
    )

    # Split schedule into two halves for two API calls
    mid = (len(schedule) + 1) // 2
    half_a = schedule[:mid]
    half_b = schedule[mid:]

    days_a = ", ".join(s["day"] for s in half_a)
    days_b = ", ".join(s["day"] for s in half_b)

    schedule_a = "\n".join(f"  - {s['day']}: {s['type']}" for s in half_a)
    schedule_b = "\n".join(f"  - {s['day']}: {s['type']}" for s in half_b)

    base_instructions = f"""Week starting {next_monday}. Full week schedule for context:
{schedule_desc}

IMPORTANT exercise variety rules:
- Upper A and Upper B MUST use different exercises (different movement patterns, same muscle groups)
- Lower A and Lower B MUST use different exercises (different movement patterns, same muscle groups)
- Follow the Upper A/B and Lower A/B exercise selection guidelines from your system prompt exactly."""

    prompt_a = f"""{base_instructions}

Generate the training plan for ONLY these days: {days_a}
Session assignments:
{schedule_a}

Return JSON with exactly two keys: "week_start" (string "{next_monday}") and "days" (array of {len(half_a)} day objects).
Pure JSON only, no markdown."""

    prompt_b = f"""{base_instructions}

Generate the training plan for ONLY these days: {days_b}
Session assignments:
{schedule_b}

Return JSON with exactly these keys: "days" (array of {len(half_b)} day objects for {days_b}), "weekly_overview", "weekly_notes", "deload_recommended".
Pure JSON only, no markdown."""

    part_a = _call_claude_json(client, system, prompt_a)
    part_b = _call_claude_json(client, system, prompt_b)

    return {
        "week_start": part_a.get("week_start", str(next_monday)),
        "weekly_overview": part_b.get("weekly_overview", ""),
        "days": part_a.get("days", []) + part_b.get("days", []),
        "weekly_notes": part_b.get("weekly_notes", ""),
        "deload_recommended": part_b.get("deload_recommended", False),
        "config": {
            "strength_days": strength_days,
            "cardio_days": cardio_days,
            "rest_days": rest_days,
        },
    }


def _call_claude_json(client: anthropic.Anthropic, system: str, prompt: str) -> dict:
    """Make a Claude call and return parsed JSON. Raises ValueError if truncated."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        temperature=0.5,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    content = response.content[0].text.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Response truncated (stop_reason={response.stop_reason}). Detail: {e}"
        ) from e


_DEFAULT_BREAKFAST_PREFS = (
    "Rotate among these 3 options each week — keep them simple, no cooking required:\n"
    "1. Overnight oats: rolled oats + 1 scoop whey protein + unsweetened almond milk + hemp/pumpkin seeds + fruit (berries or banana). Prep night before.\n"
    "2. Protein smoothie: whey protein + creatine (5g) + frozen fruit + non-fat Greek yogurt + hemp/pumpkin seeds + unsweetened almond milk. Blend and go.\n"
    "3. Eggs + toast + cottage cheese: 2-3 pasture-raised eggs (any style) + 1-2 slices Dave's Killer Bread + 1/2 cup cottage cheese. 10 min max.\n"
    "NO traditional Indian breakfast (no idli, dosa, upma, etc.). Keep it quick and high protein."
)

_DEFAULT_DINNER_PREFS = (
    "South Indian home cooking preferred: sambar with rice, kootu, poriyal, rasam, dal tadka, "
    "chana masala, rajma, paneer dishes, egg curries. Occasional non-Indian (pasta, grain bowls) is fine 1-2x/week."
)


def _training_plan_to_markdown(plan_data: dict) -> str:
    """Convert a training plan JSON dict to readable markdown for PDF export."""
    lines = []
    week = plan_data.get("week_start", "")
    lines.append(f"# Training Plan - Week of {week}\n")

    if plan_data.get("weekly_overview"):
        lines.append(plan_data["weekly_overview"])
        lines.append("")

    for day in plan_data.get("days", []):
        day_name = day.get("day", "")
        day_type = day.get("type", "")
        focus = day.get("focus", "")
        lines.append(f"## {day_name} - {day_type}\n")
        if focus:
            lines.append(f"*{focus}*\n")

        if day_type == "Rest":
            lines.append("Rest and recovery day.\n")
            continue

        exercises = day.get("exercises", [])
        for ex in exercises:
            name = ex.get("name", "")
            sets = ex.get("sets", "")
            reps = ex.get("reps", "")
            rest = ex.get("rest_seconds", "")
            setup = ex.get("tonal_setup", "")
            note = ex.get("coaching_note", "")
            prog = ex.get("progression_note", "")

            lines.append(f"### {name}\n")
            lines.append(f"- **Sets × Reps:** {sets} × {reps}" + (f"  |  **Rest:** {rest}s" if rest else ""))
            if setup:
                lines.append(f"- **Tonal Setup:** {setup}")
            if note:
                lines.append(f"- **Coaching Note:** {note}")
            if prog:
                lines.append(f"- **Progression:** {prog}")
            lines.append("")

        if day.get("session_notes"):
            lines.append(f"*Session Notes: {day['session_notes']}*\n")

    if plan_data.get("weekly_notes"):
        lines.append("## Weekly Notes\n")
        lines.append(plan_data["weekly_notes"])

    return "\n".join(lines)


def _meal_plan_to_markdown(plan_data: dict) -> str:
    """Convert a meal plan JSON dict to a readable markdown string for PDF export."""
    lines = []
    week = plan_data.get("week_start", plan_data.get("week_label", ""))
    lines.append(f"# Meal Plan - Week of {week}\n")

    calorie_target = plan_data.get("daily_target_kcal") or plan_data.get("calorie_target")
    if calorie_target:
        lines.append(f"**Daily Target:** {calorie_target} kcal\n")

    for day in plan_data.get("days", []):
        day_name = day.get("day", "")
        total_kcal = day.get("total_kcal", "")
        total_p = day.get("total_protein_g", "")
        lines.append(f"## {day_name}")
        if total_kcal:
            macro_parts = [f"{total_kcal} kcal"]
            if total_p: macro_parts.append(f"P {total_p}g")
            if day.get("total_carbs_g"): macro_parts.append(f"C {day['total_carbs_g']}g")
            if day.get("total_fat_g"): macro_parts.append(f"F {day['total_fat_g']}g")
            lines.append(f"*{' | '.join(macro_parts)}*")
        lines.append("")

        # meals is a list of meal objects
        meals = day.get("meals", [])
        if isinstance(meals, dict):
            meals = list(meals.values())

        for meal in meals:
            meal_type = meal.get("meal_type", "").capitalize()
            name = meal.get("name", "")
            lines.append(f"### {meal_type}: {name}")

            # Macros
            parts = []
            if meal.get("kcal"): parts.append(f"{meal['kcal']} kcal")
            if meal.get("protein_g"): parts.append(f"P {meal['protein_g']}g")
            if meal.get("carbs_g"): parts.append(f"C {meal['carbs_g']}g")
            if meal.get("fat_g"): parts.append(f"F {meal['fat_g']}g")
            if parts:
                lines.append(f"*{' | '.join(parts)}*")

            # Ingredients
            ingredients = meal.get("ingredients", [])
            if ingredients:
                lines.append("")
                lines.append("**Ingredients:**")
                for ing in ingredients:
                    lines.append(f"- {ing}")

            # Recipe steps
            steps = meal.get("recipe_steps", [])
            if steps:
                lines.append("")
                lines.append("**Preparation:**")
                for i, step in enumerate(steps, 1):
                    lines.append(f"{i}. {step}")

            if meal.get("prep_time_min"):
                lines.append(f"*Prep time: {meal['prep_time_min']} min*")

            lines.append("")

        lines.append("")

    if plan_data.get("shopping_list"):
        lines.append("## Shopping List\n")
        shopping = plan_data["shopping_list"]
        if isinstance(shopping, dict):
            for category, items in shopping.items():
                lines.append(f"### {category}")
                if isinstance(items, list):
                    for item in items:
                        lines.append(f"- {item}")
                lines.append("")
        elif isinstance(shopping, list):
            for item in shopping:
                lines.append(f"- {item}")
        lines.append("")

    if plan_data.get("weekly_notes"):
        lines.append("## Notes\n")
        lines.append(plan_data["weekly_notes"])

    return "\n".join(lines)


def generate_meal_plan(
    db: Session,
    calorie_target: Optional[int] = None,
    breakfast_prefs: Optional[str] = None,
    lunch_prefs: Optional[str] = None,
    dinner_prefs: Optional[str] = None,
) -> dict:
    client = _get_client()
    profile = db.query(UserProfile).first()
    latest_weight_entry = db.query(WeightLog).order_by(desc(WeightLog.date)).first()

    weight = latest_weight_entry.weight_lbs if latest_weight_entry else 181.5
    calorie_target = calorie_target or (profile.calorie_target if profile else 2200)

    protein_g = 145
    fat_g = round(calorie_target * 0.25 / 9)
    remaining = calorie_target - (protein_g * 4) - (fat_g * 9)
    carbs_g = max(100, round(remaining / 4))

    calorie_context = f"""- Daily calorie target: {calorie_target} kcal (mild deficit for fat loss)
- Estimated TDEE for 46yo male, {weight:.0f} lbs, moderately active: ~{calorie_target + 350} kcal
- Protein: {protein_g}g (priority — 140-150g/day target for muscle retention)
- Fat: {fat_g}g
- Carbs: {carbs_g}g
- Calorie breakdown: P={protein_g*4}kcal, F={fat_g*9}kcal, C={carbs_g*4}kcal"""

    breakfast_context = breakfast_prefs or _DEFAULT_BREAKFAST_PREFS
    user_prefs_section = ""
    if lunch_prefs:
        user_prefs_section += f"## Lunch Preferences\n{lunch_prefs}\n\n"
    if dinner_prefs:
        user_prefs_section += f"## Dinner Preferences\n{dinner_prefs}"
    else:
        user_prefs_section += f"## Dinner Preferences\n{_DEFAULT_DINNER_PREFS}"

    measurement_system = (profile.measurement_system if profile and profile.measurement_system else "imperial")
    measurement_note = _measurement_instruction(measurement_system)

    system = NUTRITION_SYSTEM_PROMPT.format(
        calorie_context=calorie_context,
        calorie_target=calorie_target,
        breakfast_context=breakfast_context,
        user_preferences=user_prefs_section,
    ) + f"\n\n## Units\n{measurement_note}"

    today = date.today()
    days_to_monday = (7 - today.weekday()) % 7 or 7
    next_monday = today + timedelta(days=days_to_monday)

    # Split into two calls to stay within token limits:
    # Call 1: Monday–Thursday (meals only)
    # Call 2: Friday–Sunday + shopping list + weekly notes
    prompt_a = f"""Generate a South Indian vegetarian meal plan for Monday, Tuesday, Wednesday, Thursday of the week starting {next_monday}.
Return JSON with exactly two keys: "week_start" (string "{next_monday}") and "days" (array of 4 day objects).
No shopping list. Pure JSON only, no markdown."""

    prompt_b = f"""Generate a South Indian vegetarian meal plan for Friday, Saturday, Sunday of the week starting {next_monday}.
Return JSON with exactly these keys: "daily_target_kcal" ({calorie_target}), "days" (array of 3 day objects for Fri/Sat/Sun), "shopping_list", "weekly_notes".
The shopping_list should cover ingredients for a full week of South Indian vegetarian meals.
Pure JSON only, no markdown."""

    part_a = _call_claude_json(client, system, prompt_a)
    part_b = _call_claude_json(client, system, prompt_b)

    # Merge: combine days, take metadata + shopping list from part_b
    return {
        "week_start": part_a.get("week_start", str(next_monday)),
        "daily_target_kcal": part_b.get("daily_target_kcal", calorie_target),
        "days": part_a.get("days", []) + part_b.get("days", []),
        "shopping_list": part_b.get("shopping_list", {}),
        "weekly_notes": part_b.get("weekly_notes", ""),
    }


def generate_health_insights(db: Session) -> str:
    client = _get_client()
    profile = db.query(UserProfile).first()
    latest_dexa = db.query(DexaScan).order_by(desc(DexaScan.scan_date)).first()
    latest_vo2 = db.query(Vo2MaxLog).order_by(desc(Vo2MaxLog.date)).first()
    latest_weight = db.query(WeightLog).order_by(desc(WeightLog.date)).first()

    # Weight trend (last 30 days)
    cutoff = date.today() - timedelta(days=30)
    weight_history = (
        db.query(WeightLog)
        .filter(WeightLog.date >= cutoff)
        .order_by(WeightLog.date)
        .all()
    )

    weight_trend_str = "No weight data logged yet."
    if weight_history:
        first = weight_history[0].weight_lbs
        last = weight_history[-1].weight_lbs
        delta = last - first
        weight_trend_str = f"{len(weight_history)} readings over 30 days. Start: {first} lbs → Current: {last} lbs (Δ {delta:+.1f} lbs)"

    user_profile_str = f"""- Age: 46 (DOB: Nov 11, 1979)
- Height: {(profile.height_inches or 68):.0f} inches
- Current weight: {latest_weight.weight_lbs if latest_weight else 'unknown'} lbs
- DEXA body fat: {latest_dexa.body_fat_pct if latest_dexa else 28.4}% (scan date: {str(latest_dexa.scan_date) if latest_dexa else '2026-03-13'})
- Lean mass: {latest_dexa.lean_mass_lbs if latest_dexa else 123.9} lbs
- Visceral fat: {latest_dexa.visceral_fat_lbs if latest_dexa else 1.38} lbs (target: <0.60 lbs)
- Android/Gynoid ratio: {latest_dexa.ag_ratio if latest_dexa else 1.17} (target: 0.6-0.8)
- VO2 Max: {latest_vo2.vo2max if latest_vo2 else 45.0} (goal: {profile.vo2max_goal if profile else 50.0}+ by {str(profile.goal_date) if profile else '2026-12-31'})
- Body fat goal: {profile.bf_goal_pct if profile else 18.0}% by {str(profile.goal_date) if profile else '2026-12-31'}
- Training: 4-day upper/lower split on Tonal, 2-3 cardio sessions/week
- Diet: Vegetarian + eggs, South Indian, ~{profile.calorie_target if profile else 2200} kcal/day"""

    # Try to pull 30-day Garmin trend data
    garmin_str = "Garmin data: Not connected (configure in Settings to enable sleep/HRV/body battery)."
    try:
        from services.garmin_service import garmin_service
        if garmin_service.is_authenticated():
            sleep_range = garmin_service.get_sleep_range(30)
            steps_range = garmin_service.get_steps_range(30)
            rhr_range = garmin_service.get_resting_hr_range(30)

            sections = []

            if sleep_range:
                durations = [d["duration_hours"] for d in sleep_range]
                scores = [d["score"] for d in sleep_range if d.get("score")]
                deep_vals = [d["deep_min"] for d in sleep_range if d.get("deep_min")]
                rem_vals = [d["rem_min"] for d in sleep_range if d.get("rem_min")]
                avg_dur = round(sum(durations) / len(durations), 1)
                avg_score = round(sum(scores) / len(scores)) if scores else None
                avg_deep = round(sum(deep_vals) / len(deep_vals)) if deep_vals else None
                avg_rem = round(sum(rem_vals) / len(rem_vals)) if rem_vals else None
                below_7 = sum(1 for d in durations if d < 7)
                below_65 = sum(1 for d in durations if d < 6.5)
                recent = sleep_range[-7:]
                recent_avg = round(sum(d["duration_hours"] for d in recent) / len(recent), 1)
                trend = "improving" if recent_avg > avg_dur else "declining" if recent_avg < avg_dur - 0.2 else "stable"
                last3_sleep = ", ".join(str(d["duration_hours"]) + "h" for d in sleep_range[-3:])
                sleep_section = (
                    f"Sleep (last {len(sleep_range)} days): avg {avg_dur}h/night"
                    + (f", avg score {avg_score}/100" if avg_score else "")
                    + (f", avg deep {avg_deep}min" if avg_deep else "")
                    + (f", avg REM {avg_rem}min" if avg_rem else "")
                    + f". {below_7} nights <7h, {below_65} nights <6.5h."
                    + f" Last-7-day avg: {recent_avg}h (trend: {trend})."
                    + f" Last 3 nights: {last3_sleep}"
                )
                sections.append(sleep_section)

            if steps_range:
                steps_vals = [d["steps"] for d in steps_range]
                avg_s = round(sum(steps_vals) / len(steps_vals))
                recent_steps = steps_range[-7:]
                recent_avg_s = round(sum(d["steps"] for d in recent_steps) / len(recent_steps))
                over_10k = sum(1 for s in steps_vals if s >= 10000)
                last3_steps = ", ".join(f"{d['steps']:,}" for d in steps_range[-3:])
                steps_section = (
                    f"Steps (last {len(steps_range)} days): avg {avg_s:,}/day"
                    + f", last-7-day avg {recent_avg_s:,}/day"
                    + f". {over_10k}/{len(steps_range)} days hit 10k goal."
                    + f" Last 3 days: {last3_steps}"
                )
                sections.append(steps_section)

            if rhr_range:
                rhr_vals = [d["rhr"] for d in rhr_range]
                avg_rhr = round(sum(rhr_vals) / len(rhr_vals))
                recent_rhr = rhr_range[-7:]
                recent_avg_rhr = round(sum(d["rhr"] for d in recent_rhr) / len(recent_rhr))
                trend_rhr = "improving (lower)" if recent_avg_rhr < avg_rhr - 1 else "worsening (higher)" if recent_avg_rhr > avg_rhr + 1 else "stable"
                rhr_section = (
                    f"Resting HR (last {len(rhr_range)} days): avg {avg_rhr}bpm"
                    + f", last-7-day avg {recent_avg_rhr}bpm (trend: {trend_rhr})"
                    + f". Range: {min(rhr_vals)}–{max(rhr_vals)}bpm."
                )
                sections.append(rhr_section)

            if sections:
                garmin_str = "Garmin 30-day trends:\n" + "\n".join(f"- {s}" for s in sections)
    except Exception:
        pass

    health_data_str = f"""- Weight trend (30 days): {weight_trend_str}
- DEXA scan date: {str(latest_dexa.scan_date) if latest_dexa else '2026-03-13'}
- ALMI: {latest_dexa.almi if latest_dexa else 8.6} kg/m² (target: 9.5)
- FFMI: {latest_dexa.ffmi if latest_dexa else 19.7} kg/m² (target: 21.0)
- T-Score (bone density): {latest_dexa.t_score if latest_dexa else 0.50}
- {garmin_str}"""

    measurement_system = (profile.measurement_system if profile and profile.measurement_system else "imperial")
    measurement_note = _measurement_instruction(measurement_system)

    system = HEALTH_ADVISOR_SYSTEM_PROMPT.format(
        user_profile=user_profile_str,
        health_data=health_data_str,
    ) + f"\n\n## Units\n{measurement_note}"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3500,
        temperature=0.2,
        system=system,
        messages=[{
            "role": "user",
            "content": "Analyze my health data and provide specific, actionable insights following the Attia/Huberman framework. Use all the 30-day trend data provided — reference specific numbers, trends (improving/declining/stable), nights below targets, and recent patterns. Be direct and data-driven."
        }],
    )

    return response.content[0].text


_STRAVA_TOOLS = [
    {
        "name": "get_strava_activities",
        "description": (
            "Fetch the user's cardio activities from Strava (runs, rides, walks, etc.). "
            "Returns activity name, type, date, distance, duration, and heart rate. "
            "Use this when asked about cardio sessions, runs, Zone 2 training, or any "
            "activity that is NOT a Tonal/strength workout."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max activities to return (default 10)", "default": 10},
                "activity_type": {"type": "string", "description": "Filter by Strava type: Run, Ride, Walk, Workout, etc."},
                "start_date": {"type": "string", "description": "From date inclusive (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "To date inclusive (YYYY-MM-DD)"},
            },
        },
    },
]

_HEVY_TOOLS = [
    {
        "name": "get_workouts",
        "description": "Fetch recent Hevy workouts. Returns workouts in descending date order with title, exercises, sets, weight, reps, and volume.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max number of workouts to return (default 20)", "default": 20},
                "start_date": {"type": "string", "description": "Filter from this date (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "Filter to this date (YYYY-MM-DD)"},
            },
        },
    },
    {
        "name": "get_exercises",
        "description": "Get a list of exercises the user has performed, sorted by frequency. Useful for finding exercise IDs for progress tracking.",
        "input_schema": {
            "type": "object",
            "properties": {
                "search_term": {"type": "string", "description": "Filter exercises by name"},
                "exclude_unused": {"type": "boolean", "description": "Exclude exercises never performed", "default": True},
            },
        },
    },
    {
        "name": "get_exercise_progress",
        "description": "Track performance metrics (weight, reps, volume) for specific exercises over time.",
        "input_schema": {
            "type": "object",
            "required": ["exercise_ids"],
            "properties": {
                "exercise_ids": {"type": "array", "items": {"type": "string"}, "description": "Exercise IDs to track"},
                "limit": {"type": "integer", "description": "Max sessions to return", "default": 10},
                "start_date": {"type": "string", "description": "From date (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "To date (YYYY-MM-DD)"},
            },
        },
    },
    {
        "name": "get_routines",
        "description": "Fetch the user's saved Hevy workout routines with all exercises and set configurations.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


_hevy_client_instance = None


def _get_hevy_client():
    global _hevy_client_instance
    from config import settings as cfg
    from services.hevy_api_client import HevyAPIClient
    if _hevy_client_instance is None:
        _hevy_client_instance = HevyAPIClient(cfg.hevy_api_key)
    return _hevy_client_instance


def _call_hevy_tool(tool_name: str, tool_input: dict, db: Session = None) -> str:
    try:
        from config import settings as cfg
        if not cfg.hevy_api_key:
            return json.dumps({"error": "HEVY_API_KEY not configured"})

        # get_workouts reads from the local DB (populated by Dashboard sync) so the
        # coach always sees the same data as the activity feed — no live API lag.
        if tool_name == "get_workouts" and db is not None:
            from database.models import HevyWorkout, HevyExerciseSet
            from datetime import datetime as _dt
            limit = tool_input.get("limit", 20)
            q = db.query(HevyWorkout)
            if tool_input.get("start_date"):
                q = q.filter(HevyWorkout.start_time >= _dt.fromisoformat(tool_input["start_date"]))
            if tool_input.get("end_date"):
                end = _dt.fromisoformat(tool_input["end_date"]).replace(hour=23, minute=59, second=59)
                q = q.filter(HevyWorkout.start_time <= end)
            workouts = q.order_by(desc(HevyWorkout.start_time)).limit(limit).all()
            result = []
            for w in workouts:
                sets = db.query(HevyExerciseSet).filter(HevyExerciseSet.workout_id == w.id).all()
                exercises: dict = {}
                for s in sets:
                    exercises.setdefault(s.exercise_name, []).append({
                        "type": s.set_type,
                        "weight_lbs": s.weight_lbs,
                        "reps": s.reps,
                        "rpe": s.rpe,
                    })
                result.append({
                    "id": w.id,
                    "title": w.title,
                    "start_time": w.start_time.isoformat() if w.start_time else None,
                    "duration_s": w.duration_s,
                    "volume_lbs": round(w.volume_lbs, 1) if w.volume_lbs else None,
                    "exercises": [
                        {"title": name, "sets": sets_list}
                        for name, sets_list in exercises.items()
                    ],
                })
            return json.dumps(result)

        c = _get_hevy_client()
        tool_map = {
            "get_exercises": lambda: c.get_exercises(
                search_term=tool_input.get("search_term"),
                exclude_unused=tool_input.get("exclude_unused", True),
            ),
            "get_exercise_progress": lambda: c.get_exercise_progress(
                exercise_ids=tool_input.get("exercise_ids", []),
                limit=tool_input.get("limit", 10),
                start_date=tool_input.get("start_date"),
                end_date=tool_input.get("end_date"),
            ),
            "get_routines": lambda: c.get_routines(),
        }
        fn = tool_map.get(tool_name)
        if not fn:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        return json.dumps(fn())
    except Exception as e:
        global _hevy_client_instance
        _hevy_client_instance = None
        return json.dumps({"error": str(e)})


def _call_strava_tool(tool_name: str, tool_input: dict, db: Session) -> str:
    try:
        from database.models import StravaActivity
        from datetime import datetime, timezone
        q = db.query(StravaActivity).filter(
            StravaActivity.activity_type.notin_(["Workout", "WeightTraining"])
        )
        if tool_input.get("activity_type"):
            q = q.filter(StravaActivity.activity_type == tool_input["activity_type"])
        if tool_input.get("start_date"):
            q = q.filter(
                StravaActivity.start_date >= datetime.fromisoformat(tool_input["start_date"])
            )
        if tool_input.get("end_date"):
            end = datetime.fromisoformat(tool_input["end_date"]).replace(
                hour=23, minute=59, second=59
            )
            q = q.filter(StravaActivity.start_date <= end)
        limit = tool_input.get("limit", 10)
        activities = q.order_by(desc(StravaActivity.start_date)).limit(limit).all()
        result = []
        for a in activities:
            dist_mi = round(a.distance_m / 1609.34, 2) if a.distance_m else None
            dur_min = round(a.moving_time_s / 60, 1) if a.moving_time_s else None
            pace = None
            if dist_mi and dur_min and dist_mi > 0:
                pace = f"{dur_min / dist_mi:.1f} min/mi"
            result.append({
                "name": a.name,
                "type": a.activity_type,
                "date": a.start_date.strftime("%Y-%m-%d") if a.start_date else None,
                "distance_miles": dist_mi,
                "duration_minutes": dur_min,
                "pace": pace,
                "avg_hr": a.average_hr,
                "max_hr": a.max_hr,
            })
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


def chat_with_coach(message: str, history: list, db: Session) -> str:
    client = _get_client()
    latest_dexa = db.query(DexaScan).order_by(desc(DexaScan.scan_date)).first()
    latest_vo2 = db.query(Vo2MaxLog).order_by(desc(Vo2MaxLog.date)).first()
    profile = db.query(UserProfile).first()
    active_plan = db.query(TrainingPlan).filter(TrainingPlan.is_active == True).order_by(desc(TrainingPlan.generated_at)).first()

    bf = latest_dexa.body_fat_pct if latest_dexa else 28.4
    vo2 = latest_vo2.vo2max if latest_vo2 else 45.0
    training_device = (profile.training_device if profile and profile.training_device else "tonal")
    measurement_system = (profile.measurement_system if profile and profile.measurement_system else "imperial")

    from config import settings as cfg
    hevy_note = (
        "You have access to two training data sources — use the right one for each type:\n"
        "- **Hevy tools**: ALL strength/weight training (Tonal workouts). Use for lifting volume, exercise progress, PRs.\n"
        "- **Strava tool**: CARDIO ONLY (runs, walks, rides). Strength workouts are excluded from Strava results to avoid double-counting.\n"
        "Never count the same workout from both sources."
        if cfg.hevy_api_key
        else "Hevy is not configured. You have access to Strava tools for cardio data."
    )

    device_note = _device_instruction(training_device)
    measurement_note = _measurement_instruction(measurement_system)

    from datetime import date as _date
    today_str = _date.today().isoformat()

    plan_section = ""
    if active_plan:
        try:
            plan_data = json.loads(active_plan.plan_json)
            plan_section = (
                f"\n\n## Current Training Plan (week of {active_plan.week_start})\n"
                + json.dumps(plan_data, indent=2)
            )
        except Exception:
            if active_plan.plan_markdown:
                plan_section = (
                    f"\n\n## Current Training Plan (week of {active_plan.week_start})\n"
                    + active_plan.plan_markdown
                )

    system = (
        COACH_CHAT_SYSTEM.format(current_bf=bf, current_vo2=vo2)
        + f"\n\n## Today's Date\nToday is {today_str}. Use this when filtering activities by date."
        + plan_section
        + f"\n\n{hevy_note}"
        + f"\n\n## Equipment Constraint\n{device_note}"
        + f"\n\n## Units\n{measurement_note}"
    )
    messages = history[-20:] + [{"role": "user", "content": message}]
    tools = _STRAVA_TOOLS + (_HEVY_TOOLS if cfg.hevy_api_key else [])

    _strava_tool_names = {t["name"] for t in _STRAVA_TOOLS}

    # Tool-use loop: Claude may call tools multiple times before responding
    for _ in range(5):  # max 5 tool rounds
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            temperature=0.4,
            system=system,
            messages=messages,
            tools=tools if tools else anthropic.NOT_GIVEN,
        )

        if response.stop_reason != "tool_use":
            # Final text response
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        # Execute tool calls and feed results back
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                if block.name in _strava_tool_names:
                    result_str = _call_strava_tool(block.name, block.input, db)
                else:
                    result_str = _call_hevy_tool(block.name, block.input, db)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    # Fallback: ask Claude to respond without tools
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        temperature=0.4,
        system=system,
        messages=messages,
    )
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return ""
