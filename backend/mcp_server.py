"""
Remote MCP server — exposes health data tools to Claude.app over SSE.

Routes registered in main.py:
  GET  /mcp/sse?key=<MCP_API_KEY>  — SSE handshake (key-authenticated)
  POST /mcp/messages               — MCP JSON-RPC messages
"""
import asyncio
import json
import uuid as _uuid_mod
from collections import defaultdict
from contextvars import ContextVar
from datetime import date, datetime, timedelta
from typing import Any, Optional

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp import types
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Scope, Receive, Send

# Context variable to hold the current user_id for the duration of an MCP session.
# Set in sse_endpoint after validating the MCP API key.
_current_user_id: ContextVar[Optional[_uuid_mod.UUID]] = ContextVar("_current_user_id", default=None)


def _get_user_id() -> Optional[_uuid_mod.UUID]:
    """Return the user_id for the current MCP session, or None if not set."""
    return _current_user_id.get()


class _AlreadySentResponse(Response):
    """Returned by MCP handlers after the transport has already written the response.
    Starlette calls await response(...) after the handler returns — this no-ops that call."""
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        pass

from config import settings
from database.engine import SessionLocal
from database.models import (
    WeightLog, HevyWorkout, HevyExerciseSet,
    TrainingPlan, GarminDailyCache, BodyCompositionLog,
    Vo2MaxLog, NutritionLog, HealthInsight, UserProfile,
    MealPlan, Supplement, SupplementLog, WeeklyCheckin,
)

server = Server("health-coach")
sse = SseServerTransport("/mcp/messages")

# Default meal preference strings (matches Nutrition.tsx defaults)
_BREAKFAST_PREFS = (
    "Rotate among these options — keep them quick, no cooking:\n"
    "1. Overnight oats: rolled oats + whey protein + unsweetened almond milk + hemp/pumpkin seeds + berries\n"
    "2. Protein smoothie: whey protein + creatine + frozen fruit + non-fat Greek yogurt + hemp/pumpkin seeds + unsweetened almond milk\n"
    "3. Eggs + toast + cottage cheese: 2-3 pasture-raised eggs + Dave's Killer Bread + cottage cheese\n"
    "No traditional Indian breakfast (no idli, dosa, upma)."
)
_LUNCH_PREFS = "Lunch is usually previous night's dinner"
_DINNER_PREFS = (
    "South Indian home cooking: sambar with rice, kootu, poriyal, rasam, dal tadka, chana masala, "
    "rajma, paneer dishes, egg curries. Occasional non-Indian (pasta, grain bowls) 1-2x/week is fine."
)


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="log_meal",
            description="Log a meal with estimated macros. Use this after eating to track nutrition.",
            inputSchema={
                "type": "object",
                "properties": {
                    "meal_type": {
                        "type": "string",
                        "enum": ["breakfast", "lunch", "dinner", "snack"],
                        "description": "Type of meal",
                    },
                    "name": {
                        "type": "string",
                        "description": "Name of the meal or food (e.g. 'Overnight oats with berries')",
                    },
                    "estimated_kcal": {
                        "type": "integer",
                        "description": "Estimated calories",
                    },
                    "estimated_protein_g": {
                        "type": "number",
                        "description": "Estimated protein in grams",
                    },
                    "estimated_carbs_g": {
                        "type": "number",
                        "description": "Estimated carbohydrates in grams",
                    },
                    "estimated_fat_g": {
                        "type": "number",
                        "description": "Estimated fat in grams",
                    },
                    "date": {
                        "type": "string",
                        "description": "ISO date string (YYYY-MM-DD). Defaults to today.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description or notes about the meal",
                    },
                },
                "required": ["meal_type", "name", "estimated_kcal", "estimated_protein_g", "estimated_carbs_g", "estimated_fat_g"],
            },
        ),
        types.Tool(
            name="get_nutrition_log",
            description="Get all meals logged for a specific date and daily macro totals.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "ISO date string (YYYY-MM-DD). Defaults to today.",
                    },
                },
            },
        ),
        types.Tool(
            name="generate_meal_plan",
            description="Generate a new AI-powered 7-day vegetarian meal plan. Saves to the app.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="get_todays_workout",
            description="Get today's scheduled workout from the active training plan, including exercises, sets, reps, and coaching notes.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="get_recent_workouts",
            description="Get recent Hevy workout history with exercises and weights lifted.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back. Defaults to 7.",
                    },
                },
            },
        ),
        types.Tool(
            name="get_exercise_stats",
            description="Get weekly progress for a specific exercise: max weight, estimated 1RM, and PR markers.",
            inputSchema={
                "type": "object",
                "properties": {
                    "exercise_name": {
                        "type": "string",
                        "description": "Exact exercise name as recorded in Hevy (e.g. 'Chest Press', 'Cable Row')",
                    },
                    "weeks": {
                        "type": "integer",
                        "description": "Number of weeks of history. Defaults to 13.",
                    },
                },
                "required": ["exercise_name"],
            },
        ),
        types.Tool(
            name="generate_training_plan",
            description="Generate a new AI-powered weekly training plan for Tonal. Saves to the app.",
            inputSchema={
                "type": "object",
                "properties": {
                    "strength_days": {
                        "type": "integer",
                        "description": "Number of strength training days per week. Defaults to 4.",
                    },
                    "cardio_days": {
                        "type": "integer",
                        "description": "Number of cardio days per week. Defaults to 2.",
                    },
                    "rest_days": {
                        "type": "integer",
                        "description": "Number of rest days per week. Defaults to 1.",
                    },
                },
            },
        ),
        types.Tool(
            name="get_health_metrics",
            description="Get a table of recent daily health metrics: sleep, steps, and resting heart rate.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days of history. Defaults to 14.",
                    },
                },
            },
        ),
        types.Tool(
            name="get_health_summary",
            description="Get a full health summary: current weight, body composition, VO2 max, and recent Garmin metrics.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="get_health_recommendations",
            description="Get the latest AI-generated health recommendations and insights.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="log_weight",
            description="Log a body weight measurement.",
            inputSchema={
                "type": "object",
                "properties": {
                    "weight_lbs": {
                        "type": "number",
                        "description": "Body weight in pounds",
                    },
                    "date": {
                        "type": "string",
                        "description": "ISO date string (YYYY-MM-DD). Defaults to today.",
                    },
                },
                "required": ["weight_lbs"],
            },
        ),
        types.Tool(
            name="sync_data",
            description="Trigger a sync of Strava activities and Hevy workouts to the local database.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="get_meal_plan_for_day",
            description="Get the planned meals for a specific day from the active meal plan. Use this to answer 'what should I eat today?' or 'what's for dinner tonight?'",
            inputSchema={
                "type": "object",
                "properties": {
                    "day": {
                        "type": "string",
                        "description": "Day of the week (e.g. 'Monday', 'Tuesday'). Defaults to today.",
                    },
                },
            },
        ),
        types.Tool(
            name="log_supplement",
            description="Mark one or more supplements as taken for today (or a specific date). Use this when the user says they took a supplement, vitamin, or medication.",
            inputSchema={
                "type": "object",
                "properties": {
                    "supplement_name": {
                        "type": "string",
                        "description": "Name of the supplement (e.g. 'Vitamin D', 'Omega-3'). Will match against existing supplements; creates a new one if not found.",
                    },
                    "date": {
                        "type": "string",
                        "description": "ISO date (YYYY-MM-DD). Defaults to today.",
                    },
                },
                "required": ["supplement_name"],
            },
        ),
        types.Tool(
            name="get_supplement_log",
            description="Show which supplements were taken on a given date and which were missed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "ISO date (YYYY-MM-DD). Defaults to today.",
                    },
                },
            },
        ),
        types.Tool(
            name="submit_weekly_checkin",
            description=(
                "Submit a weekly self-assessment (1–5 ratings + optional journal notes). "
                "Saves to the current week's check-in and feeds into Coach and Health Advisor context. "
                "All rating fields are optional — only provided fields are updated."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "training_adherence": {
                        "type": "integer",
                        "description": "1–5. How many planned workouts were completed? 1=missed most, 5=hit all.",
                    },
                    "energy_level": {
                        "type": "integer",
                        "description": "1–5. Overall energy levels this week. 1=very low, 5=very high.",
                    },
                    "sleep_quality": {
                        "type": "integer",
                        "description": "1–5. Subjective sleep quality. 1=poor, 5=excellent.",
                    },
                    "diet_adherence": {
                        "type": "integer",
                        "description": "1–5. How well did you stick to your nutrition plan? 1=off track, 5=fully on target.",
                    },
                    "stress_level": {
                        "type": "integer",
                        "description": "1–5. Subjective stress. 1=very low, 5=very high.",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Free-text journal entry — anything else on your mind this week.",
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    handlers = {
        "log_meal": _log_meal,
        "get_nutrition_log": _get_nutrition_log,
        "generate_meal_plan": _generate_meal_plan,
        "get_todays_workout": _get_todays_workout,
        "get_recent_workouts": _get_recent_workouts,
        "get_exercise_stats": _get_exercise_stats,
        "generate_training_plan": _generate_training_plan,
        "get_health_metrics": _get_health_metrics,
        "get_health_summary": _get_health_summary,
        "get_health_recommendations": _get_health_recommendations,
        "log_weight": _log_weight,
        "sync_data": _sync_data,
        "get_meal_plan_for_day": _get_meal_plan_for_day,
        "log_supplement": _log_supplement,
        "get_supplement_log": _get_supplement_log,
        "submit_weekly_checkin": _submit_weekly_checkin,
    }
    handler = handlers.get(name)
    if not handler:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]
    return await handler(arguments)


# ── Tool implementations ──────────────────────────────────────────────────────

async def _log_meal(args: dict[str, Any]) -> list[types.TextContent]:
    raw_date = args.get("date")
    target_date = date.fromisoformat(raw_date) if raw_date else date.today()
    user_id = _get_user_id()

    db = SessionLocal()
    try:
        row = NutritionLog(
            user_id=user_id,
            date=target_date,
            meal_type=args["meal_type"],
            name=args["name"],
            description=args.get("description"),
            kcal=int(args["estimated_kcal"]),
            protein_g=float(args["estimated_protein_g"]),
            carbs_g=float(args["estimated_carbs_g"]),
            fat_g=float(args["estimated_fat_g"]),
            source="mcp",
            logged_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        text = (
            f"Logged {args['name']} ({args['meal_type']}) on {target_date.isoformat()}. "
            f"Macros: {row.kcal} kcal | P: {row.protein_g}g | C: {row.carbs_g}g | F: {row.fat_g}g"
        )
    finally:
        db.close()
    return [types.TextContent(type="text", text=text)]


async def _get_nutrition_log(args: dict[str, Any]) -> list[types.TextContent]:
    raw_date = args.get("date")
    target_date = date.fromisoformat(raw_date) if raw_date else date.today()
    user_id = _get_user_id()

    db = SessionLocal()
    try:
        q = db.query(NutritionLog).filter(NutritionLog.date == target_date)
        if user_id is not None:
            q = q.filter(NutritionLog.user_id == user_id)
        rows = q.order_by(NutritionLog.logged_at).all()
        if not rows:
            return [types.TextContent(
                type="text",
                text=f"No meals logged for {target_date.isoformat()}. Tell Claude on your phone what you ate.",
            )]

        lines = [f"Food log for {target_date.isoformat()}:", ""]
        total_kcal = total_p = total_c = total_f = 0.0
        for r in rows:
            lines.append(f"  [{r.meal_type.upper()}] {r.name}")
            lines.append(f"    {r.kcal} kcal | P: {r.protein_g}g | C: {r.carbs_g}g | F: {r.fat_g}g")
            if r.description:
                lines.append(f"    Note: {r.description}")
            total_kcal += r.kcal
            total_p += r.protein_g
            total_c += r.carbs_g
            total_f += r.fat_g

        lines.append("")
        lines.append(
            f"Daily totals: {int(total_kcal)} kcal | P: {round(total_p, 1)}g | C: {round(total_c, 1)}g | F: {round(total_f, 1)}g"
        )
    finally:
        db.close()
    return [types.TextContent(type="text", text="\n".join(lines))]


async def _generate_meal_plan(args: dict[str, Any]) -> list[types.TextContent]:
    from services import claude_service
    user_id = _get_user_id()

    db = SessionLocal()
    try:
        q_profile = db.query(UserProfile)
        if user_id is not None:
            q_profile = q_profile.filter(UserProfile.user_id == user_id)
        profile = q_profile.first()
        calorie_target = profile.calorie_target if profile and profile.calorie_target else 2200

        plan_data = await asyncio.to_thread(
            claude_service.generate_meal_plan,
            db,
            calorie_target,
            _BREAKFAST_PREFS,
            _LUNCH_PREFS,
            _DINNER_PREFS,
            user_id,
        )

        week_start = plan_data.get("week_start", str(date.today()))
        days = plan_data.get("days", [])

        # Persist to DB (deactivate old for this user, save new)
        q_mp = db.query(MealPlan)
        if user_id is not None:
            q_mp = q_mp.filter(MealPlan.user_id == user_id)
        q_mp.update({"is_active": False})
        try:
            ws = date.fromisoformat(week_start)
        except ValueError:
            ws = date.today()

        plan = MealPlan(
            user_id=user_id,
            week_start=ws,
            plan_json=json.dumps(plan_data),
            calorie_target=plan_data.get("daily_target_kcal", calorie_target),
            is_active=True,
        )
        db.add(plan)
        db.commit()

        text = f"New meal plan generated for week of {week_start}. {len(days)} days planned. Open the app to view details."
    finally:
        db.close()
    return [types.TextContent(type="text", text=text)]


async def _get_todays_workout(args: dict[str, Any]) -> list[types.TextContent]:
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        from sqlalchemy import desc as sa_desc
        q = db.query(TrainingPlan).filter(TrainingPlan.is_active == True)
        if user_id is not None:
            q = q.filter(TrainingPlan.user_id == user_id)
        plan = q.order_by(sa_desc(TrainingPlan.generated_at)).first()
        if not plan or not plan.plan_json:
            return [types.TextContent(type="text", text="No active training plan. Generate one from the Coach page.")]

        plan_data = json.loads(plan.plan_json)
        today_name = datetime.today().strftime("%A")

        days = plan_data.get("days", [])
        today_day = next((d for d in days if d.get("day") == today_name), None)

        if not today_day:
            return [types.TextContent(type="text", text=f"Rest day — no workout scheduled for {today_name}.")]

        lines = [f"Today's workout ({today_name} — {today_day.get('session_type', '')}):"]
        lines.append(f"Focus: {today_day.get('focus', '')}")
        lines.append(f"Duration: {today_day.get('duration_min', '?')} min")
        lines.append("")

        for ex in today_day.get("exercises", []):
            lines.append(f"  {ex.get('name', 'Unknown')}")
            lines.append(f"    Sets: {ex.get('sets', '?')} x {ex.get('reps', '?')} reps")
            lines.append(f"    Rest: {ex.get('rest_seconds', '?')}s")
            if ex.get("tonal_setup"):
                lines.append(f"    Setup: {ex['tonal_setup']}")
            if ex.get("coaching_note"):
                lines.append(f"    Note: {ex['coaching_note']}")
            lines.append("")
    finally:
        db.close()
    return [types.TextContent(type="text", text="\n".join(lines))]


async def _get_recent_workouts(args: dict[str, Any]) -> list[types.TextContent]:
    days = int(args.get("days", 7))
    cutoff = datetime.now() - timedelta(days=days)
    user_id = _get_user_id()

    db = SessionLocal()
    try:
        q = db.query(HevyWorkout).filter(HevyWorkout.start_time >= cutoff)
        if user_id is not None:
            q = q.filter(HevyWorkout.user_id == user_id)
        workouts = q.order_by(HevyWorkout.start_time.desc()).all()
        if not workouts:
            return [types.TextContent(type="text", text=f"No workouts in the last {days} days.")]

        lines = [f"Recent workouts (last {days} days):", ""]
        for w in workouts:
            dur_min = round((w.duration_s or 0) / 60)
            vol = round(w.volume_lbs or 0)
            lines.append(f"  {w.title or 'Workout'} — {w.start_time.strftime('%a %b %d')}")
            lines.append(f"    Duration: {dur_min} min | Volume: {vol} lbs")

            # Group exercise sets
            exercise_map: dict[str, list] = defaultdict(list)
            for s in w.exercise_sets:
                exercise_map[s.exercise_name].append(s)

            for ex_name, sets in exercise_map.items():
                set_strs = []
                for s in sorted(sets, key=lambda x: x.set_index or 0):
                    if s.weight_lbs and s.reps:
                        set_strs.append(f"{s.weight_lbs}x{s.reps}")
                if set_strs:
                    lines.append(f"    {ex_name}: {', '.join(set_strs)}")
            lines.append("")
    finally:
        db.close()
    return [types.TextContent(type="text", text="\n".join(lines))]


async def _get_exercise_stats(args: dict[str, Any]) -> list[types.TextContent]:
    exercise_name = args["exercise_name"]
    weeks = int(args.get("weeks", 13))
    user_id = _get_user_id()

    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    cutoff = this_monday - timedelta(weeks=weeks - 1)
    cutoff_dt = datetime.combine(cutoff, datetime.min.time())

    db = SessionLocal()
    try:
        q = (
            db.query(HevyExerciseSet, HevyWorkout.start_time)
            .join(HevyWorkout, HevyWorkout.id == HevyExerciseSet.workout_id)
            .filter(HevyExerciseSet.exercise_name == exercise_name)
            .filter(HevyExerciseSet.set_type == "normal")
            .filter(HevyExerciseSet.weight_lbs.isnot(None))
            .filter(HevyExerciseSet.weight_lbs > 0)
            .filter(HevyWorkout.start_time >= cutoff_dt)
        )
        if user_id is not None:
            q = q.filter(HevyExerciseSet.user_id == user_id)
        sets = q.order_by(HevyWorkout.start_time).all()

        if not sets:
            return [types.TextContent(
                type="text",
                text=f"No data found for '{exercise_name}' in the last {weeks} weeks.",
            )]

        weeks_map: dict = defaultdict(lambda: {"max_weight_lbs": 0.0, "est_1rm": 0.0})
        for s, start_time in sets:
            d = start_time.date()
            monday = (d - timedelta(days=d.weekday())).isoformat()
            weight = s.weight_lbs or 0
            reps = s.reps or 1
            epley = weight * (1 + reps / 30.0)
            weeks_map[monday]["max_weight_lbs"] = max(weeks_map[monday]["max_weight_lbs"], weight)
            weeks_map[monday]["est_1rm"] = max(weeks_map[monday]["est_1rm"], epley)

        lines = [f"Weekly progress for {exercise_name}:", ""]
        lines.append(f"{'Week':12} | {'Max Weight':12} | {'Est 1RM':10} | PR?")
        lines.append("-" * 50)

        running_max = 0.0
        for monday in sorted(weeks_map.keys()):
            v = weeks_map[monday]
            w = round(v["max_weight_lbs"], 1)
            est = round(v["est_1rm"], 1)
            is_pr = w > running_max
            if is_pr:
                running_max = w
            pr_marker = " PR" if is_pr else ""
            lines.append(f"{monday:12} | {w:>10} lbs | {est:>8} lbs |{pr_marker}")
    finally:
        db.close()
    return [types.TextContent(type="text", text="\n".join(lines))]


async def _generate_training_plan(args: dict[str, Any]) -> list[types.TextContent]:
    from services import claude_service
    user_id = _get_user_id()

    strength_days = int(args.get("strength_days", 4))
    cardio_days = int(args.get("cardio_days", 2))
    rest_days = int(args.get("rest_days", 1))

    db = SessionLocal()
    try:
        plan_data = await asyncio.to_thread(
            claude_service.generate_training_plan,
            db,
            strength_days,
            cardio_days,
            rest_days,
            user_id,
        )

        week_start = plan_data.get("week_start", str(date.today()))

        # Persist to DB (deactivate old for this user)
        q_tp = db.query(TrainingPlan)
        if user_id is not None:
            q_tp = q_tp.filter(TrainingPlan.user_id == user_id)
        q_tp.update({"is_active": False})
        try:
            ws = date.fromisoformat(week_start)
        except ValueError:
            ws = date.today()

        plan = TrainingPlan(
            user_id=user_id,
            week_start=ws,
            plan_json=json.dumps(plan_data),
            is_active=True,
        )
        db.add(plan)
        db.commit()

        text = f"New training plan generated for week of {week_start}. Open the app to view details."
    finally:
        db.close()
    return [types.TextContent(type="text", text=text)]


async def _get_health_metrics(args: dict[str, Any]) -> list[types.TextContent]:
    days = int(args.get("days", 14))
    cutoff = date.today() - timedelta(days=days)
    user_id = _get_user_id()

    db = SessionLocal()
    try:
        q = db.query(GarminDailyCache).filter(GarminDailyCache.date >= cutoff)
        if user_id is not None:
            q = q.filter(GarminDailyCache.user_id == user_id)
        rows = q.order_by(GarminDailyCache.date.desc()).all()
        if not rows:
            return [types.TextContent(
                type="text",
                text=f"No Garmin data in the last {days} days. Sync Garmin from the app.",
            )]

        lines = [f"Health metrics (last {days} days):", ""]
        lines.append(f"{'Date':12} | {'Sleep':10} | {'Score':7} | {'Steps':8} | {'RHR':5}")
        lines.append("-" * 55)
        for r in rows:
            sleep_str = f"{r.sleep_duration_hours:.1f}h" if r.sleep_duration_hours else "—"
            score_str = str(r.sleep_score) if r.sleep_score else "—"
            steps_str = str(r.steps) if r.steps else "—"
            rhr_str = str(r.resting_hr) if r.resting_hr else "—"
            lines.append(
                f"{r.date.isoformat():12} | {sleep_str:10} | {score_str:7} | {steps_str:8} | {rhr_str}"
            )
    finally:
        db.close()
    return [types.TextContent(type="text", text="\n".join(lines))]


async def _get_health_summary(args: dict[str, Any]) -> list[types.TextContent]:
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        from sqlalchemy import desc as sa_desc

        def _uid_filter(q, model):
            if user_id is not None:
                return q.filter(model.user_id == user_id)
            return q

        latest_weight = _uid_filter(db.query(WeightLog), WeightLog).order_by(sa_desc(WeightLog.date)).first()
        latest_bc = _uid_filter(db.query(BodyCompositionLog), BodyCompositionLog).order_by(sa_desc(BodyCompositionLog.date)).first()
        latest_vo2 = _uid_filter(db.query(Vo2MaxLog), Vo2MaxLog).order_by(sa_desc(Vo2MaxLog.date)).first()
        profile = _uid_filter(db.query(UserProfile), UserProfile).first()

        # Last 7 days of health cache data
        cutoff = date.today() - timedelta(days=7)
        garmin_rows = _uid_filter(
            db.query(GarminDailyCache).filter(GarminDailyCache.date >= cutoff),
            GarminDailyCache,
        ).order_by(GarminDailyCache.date.desc()).all()

        lines = ["Health Summary", "=" * 40, ""]

        # Weight
        if latest_weight:
            lines.append(f"Weight: {latest_weight.weight_lbs} lbs (as of {latest_weight.date})")
        else:
            lines.append("Weight: No data")

        # Body composition
        if latest_bc:
            lines.append(f"Body Fat: {latest_bc.body_fat_pct}% (as of {latest_bc.date})")
            if latest_bc.lean_mass_lbs:
                lines.append(f"Lean Mass: {latest_bc.lean_mass_lbs} lbs")
        else:
            lines.append("Body composition: No data recorded")

        # VO2 max
        if latest_vo2:
            goal = profile.vo2max_goal if profile else 50.0
            lines.append(f"VO2 Max: {latest_vo2.vo2max} (goal: {goal}+)")
        else:
            lines.append("VO2 Max: No data")

        # Goals
        if profile:
            lines.append("")
            lines.append(f"Goals by {profile.goal_date}:")
            lines.append(f"  Body fat: {profile.bf_goal_pct}%")
            lines.append(f"  VO2 max: {profile.vo2max_goal}+")

        # Garmin summary
        if garmin_rows:
            lines.append("")
            lines.append("Last 7 days (Garmin):")
            sleep_vals = [r.sleep_duration_hours for r in garmin_rows if r.sleep_duration_hours]
            step_vals = [r.steps for r in garmin_rows if r.steps]
            rhr_vals = [r.resting_hr for r in garmin_rows if r.resting_hr]
            if sleep_vals:
                lines.append(f"  Avg sleep: {round(sum(sleep_vals)/len(sleep_vals), 1)}h")
            if step_vals:
                lines.append(f"  Avg steps: {int(sum(step_vals)/len(step_vals))}")
            if rhr_vals:
                lines.append(f"  Avg RHR: {int(sum(rhr_vals)/len(rhr_vals))} bpm")
        else:
            lines.append("")
            lines.append("Garmin: No recent data (sync from app)")
    finally:
        db.close()
    return [types.TextContent(type="text", text="\n".join(lines))]


async def _get_health_recommendations(args: dict[str, Any]) -> list[types.TextContent]:
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        from sqlalchemy import desc as sa_desc
        q = db.query(HealthInsight)
        if user_id is not None:
            q = q.filter(HealthInsight.user_id == user_id)
        insight = q.order_by(sa_desc(HealthInsight.generated_at)).first()
        if not insight:
            text = "No health insights generated yet. Open the app and generate insights from the Health Advisor page."
        else:
            text = insight.content_md
    finally:
        db.close()
    return [types.TextContent(type="text", text=text)]


async def _log_weight(args: dict[str, Any]) -> list[types.TextContent]:
    weight_lbs = float(args["weight_lbs"])
    raw_date = args.get("date")
    target_date = date.fromisoformat(raw_date) if raw_date else date.today()
    user_id = _get_user_id()

    db = SessionLocal()
    try:
        q = db.query(WeightLog).filter(WeightLog.date == target_date)
        if user_id is not None:
            q = q.filter(WeightLog.user_id == user_id)
        existing = q.first()
        if existing:
            old_weight = existing.weight_lbs
            existing.weight_lbs = weight_lbs
            db.commit()
            text = f"Updated weight for {target_date.isoformat()}: {old_weight} lbs → {weight_lbs} lbs"
        else:
            row = WeightLog(user_id=user_id, date=target_date, weight_lbs=weight_lbs, source="mcp")
            db.add(row)
            db.commit()
            text = f"Logged weight: {weight_lbs} lbs on {target_date.isoformat()}"
    finally:
        db.close()
    return [types.TextContent(type="text", text=text)]


async def _sync_data(args: dict[str, Any]) -> list[types.TextContent]:
    results = {"strava": "skipped", "hevy": "skipped"}
    user_id = _get_user_id()

    db = SessionLocal()
    try:
        # Strava sync
        try:
            from services.strava_service import StravaService
            svc = StravaService(db, user_id)
            if svc.is_connected():
                r = await asyncio.to_thread(svc.sync_activities)
                results["strava"] = f"+{r['added']} added, {r['updated']} updated, {r['deleted']} deleted"
        except Exception as e:
            results["strava"] = f"error: {str(e)}"

        # Hevy sync
        try:
            import services.hevy_service as hevy_svc
            profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first() if user_id else None
            api_key = profile.hevy_api_key if profile else None
            if api_key:
                r = await asyncio.to_thread(hevy_svc.sync_workouts, db, user_id, api_key)
                results["hevy"] = f"+{r['added']} added, {r['updated']} updated, {r['deleted']} deleted"
        except Exception as e:
            results["hevy"] = f"error: {str(e)}"
    finally:
        db.close()

    text = f"Sync complete. Hevy: {results['hevy']}. Strava: {results['strava']}."
    return [types.TextContent(type="text", text=text)]


async def _get_meal_plan_for_day(args: dict[str, Any]) -> list[types.TextContent]:
    day_name = args.get("day") or datetime.today().strftime("%A")
    day_name = day_name.strip().title()
    user_id = _get_user_id()

    db = SessionLocal()
    try:
        from sqlalchemy import desc as sa_desc
        q = db.query(MealPlan).filter(MealPlan.is_active == True)
        if user_id is not None:
            q = q.filter(MealPlan.user_id == user_id)
        plan = q.order_by(sa_desc(MealPlan.generated_at)).first()
        if not plan or not plan.plan_json:
            return [types.TextContent(type="text", text="No active meal plan. Generate one from the Nutrition page.")]

        plan_data = json.loads(plan.plan_json)
        days = plan_data.get("days", [])
        today_data = next((d for d in days if d.get("day", "").title() == day_name), None)

        if not today_data:
            available = ", ".join(d.get("day", "") for d in days)
            return [types.TextContent(
                type="text",
                text=f"No meals planned for {day_name}. Available days: {available}.",
            )]

        meals = today_data.get("meals", [])
        lines = [
            f"Meal plan for {day_name}",
            f"Daily target: {plan_data.get('daily_target_kcal', '?')} kcal",
            f"Day totals: {today_data.get('total_kcal', '?')} kcal | "
            f"P: {today_data.get('total_protein_g', '?')}g | "
            f"C: {today_data.get('total_carbs_g', '?')}g | "
            f"F: {today_data.get('total_fat_g', '?')}g",
            "",
        ]

        MEAL_ORDER = ["breakfast", "lunch", "snack", "dinner", "dessert"]
        meals_sorted = sorted(meals, key=lambda m: MEAL_ORDER.index(m.get("meal_type", "snack"))
                              if m.get("meal_type") in MEAL_ORDER else 99)

        for meal in meals_sorted:
            lines.append(f"[{meal.get('meal_type', '').upper()}] {meal.get('name', '')}")
            lines.append(
                f"  {meal.get('kcal', '?')} kcal | "
                f"P: {meal.get('protein_g', '?')}g | "
                f"C: {meal.get('carbs_g', '?')}g | "
                f"F: {meal.get('fat_g', '?')}g"
            )
            if meal.get("prep_time_min"):
                lines.append(f"  Prep time: {meal['prep_time_min']} min")
            ingredients = meal.get("ingredients", [])
            if ingredients:
                lines.append(f"  Ingredients: {', '.join(ingredients)}")
            if meal.get("bobby_parish_notes"):
                lines.append(f"  Note: {meal['bobby_parish_notes']}")
            lines.append("")
    finally:
        db.close()

    return [types.TextContent(type="text", text="\n".join(lines))]


async def _log_supplement(args: dict[str, Any]) -> list[types.TextContent]:
    supplement_name = args.get("supplement_name", "").strip()
    if not supplement_name:
        return [types.TextContent(type="text", text="supplement_name is required.")]

    raw_date = args.get("date")
    target_date = date.fromisoformat(raw_date) if raw_date else date.today()
    user_id = _get_user_id()

    db = SessionLocal()
    try:
        # Find existing active supplement (case-insensitive, scoped to user)
        q_supp = db.query(Supplement).filter(Supplement.is_active == True)
        if user_id is not None:
            q_supp = q_supp.filter(Supplement.user_id == user_id)
        supplements = q_supp.all()
        match = next(
            (s for s in supplements if s.name.lower() == supplement_name.lower()), None
        )

        if not match:
            match = Supplement(user_id=user_id, name=supplement_name)
            db.add(match)
            db.commit()
            db.refresh(match)
            created = True
        else:
            created = False

        q_existing = db.query(SupplementLog).filter(
            SupplementLog.supplement_id == match.id,
            SupplementLog.date == target_date,
        )
        if user_id is not None:
            q_existing = q_existing.filter(SupplementLog.user_id == user_id)
        existing = q_existing.first()

        if existing:
            return [types.TextContent(
                type="text",
                text=f"✓ {match.name} was already logged for {target_date}.",
            )]

        log = SupplementLog(user_id=user_id, supplement_id=match.id, date=target_date)
        db.add(log)
        db.commit()

        prefix = f"Added '{match.name}' to your supplement list and logged" if created else "Logged"
        dosage_str = f" ({match.dosage})" if match.dosage else ""
        return [types.TextContent(
            type="text",
            text=f"✓ {prefix} {match.name}{dosage_str} for {target_date}.",
        )]
    finally:
        db.close()


async def _get_supplement_log(args: dict[str, Any]) -> list[types.TextContent]:
    raw_date = args.get("date")
    target_date = date.fromisoformat(raw_date) if raw_date else date.today()
    user_id = _get_user_id()

    db = SessionLocal()
    try:
        q_supp = db.query(Supplement).filter(Supplement.is_active == True)
        if user_id is not None:
            q_supp = q_supp.filter(Supplement.user_id == user_id)
        all_supplements = q_supp.all()

        q_log = db.query(SupplementLog).filter(SupplementLog.date == target_date)
        if user_id is not None:
            q_log = q_log.filter(SupplementLog.user_id == user_id)
        taken_ids = {log.supplement_id for log in q_log.all()}

        if not all_supplements:
            return [types.TextContent(type="text", text="No supplements configured yet.")]

        taken = [s for s in all_supplements if s.id in taken_ids]
        missed = [s for s in all_supplements if s.id not in taken_ids]

        lines = [f"Supplement log for {target_date}", ""]
        if taken:
            lines.append("✓ Taken:")
            for s in taken:
                dosage = f" — {s.dosage}" if s.dosage else ""
                lines.append(f"  • {s.name}{dosage}")
        if missed:
            lines.append("")
            lines.append("✗ Not yet taken:")
            for s in missed:
                dosage = f" — {s.dosage}" if s.dosage else ""
                lines.append(f"  • {s.name}{dosage}")

        return [types.TextContent(type="text", text="\n".join(lines))]
    finally:
        db.close()


async def _submit_weekly_checkin(args: dict[str, Any]) -> list[types.TextContent]:
    def _monday(d: date) -> date:
        return d - timedelta(days=d.weekday())

    week_start = _monday(date.today())
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        # Validate ratings
        for field in ("training_adherence", "energy_level", "sleep_quality", "diet_adherence", "stress_level"):
            val = args.get(field)
            if val is not None and not (1 <= int(val) <= 5):
                return [types.TextContent(type="text", text=f"Error: {field} must be between 1 and 5.")]

        q = db.query(WeeklyCheckin).filter(WeeklyCheckin.week_start == week_start)
        if user_id is not None:
            q = q.filter(WeeklyCheckin.user_id == user_id)
        existing = q.first()
        if existing:
            for field in ("training_adherence", "energy_level", "sleep_quality", "diet_adherence", "stress_level", "notes"):
                val = args.get(field)
                if val is not None:
                    setattr(existing, field, val)
            db.commit()
            db.refresh(existing)
            row = existing
        else:
            row = WeeklyCheckin(
                user_id=user_id,
                week_start=week_start,
                training_adherence=args.get("training_adherence"),
                energy_level=args.get("energy_level"),
                sleep_quality=args.get("sleep_quality"),
                diet_adherence=args.get("diet_adherence"),
                stress_level=args.get("stress_level"),
                notes=args.get("notes"),
            )
            db.add(row)
            db.commit()
            db.refresh(row)

        labels = {1: "★☆☆☆☆", 2: "★★☆☆☆", 3: "★★★☆☆", 4: "★★★★☆", 5: "★★★★★"}
        lines = [f"✓ Weekly check-in saved for week of {week_start}", ""]
        for field, title in [
            ("training_adherence", "Training adherence"),
            ("energy_level", "Energy levels"),
            ("sleep_quality", "Sleep quality"),
            ("diet_adherence", "Diet adherence"),
            ("stress_level", "Stress level"),
        ]:
            val = getattr(row, field)
            lines.append(f"  {title}: {labels.get(val, '—') if val else '—'} ({val}/5)" if val else f"  {title}: not rated")
        if row.notes:
            lines.append(f"\n  Notes: {row.notes}")
        lines.append("\nThis will be included in your next Coach and Health Advisor session.")
        return [types.TextContent(type="text", text="\n".join(lines))]
    finally:
        db.close()


# ── ASGI endpoint handlers ────────────────────────────────────────────────────

async def sse_endpoint(request: Request):
    """SSE handshake — validates per-user MCP API key, then starts MCP session."""
    key = request.query_params.get("key", "")
    if not key:
        return Response("Unauthorized", status_code=401)

    # Resolve user_id from the per-user key stored in UserProfile.
    user_id: Optional[_uuid_mod.UUID] = None
    db = SessionLocal()
    try:
        from database.models import UserProfile as _UP
        profile = db.query(_UP).filter(_UP.mcp_api_key == key).first()
        if profile:
            user_id = profile.user_id
        else:
            return Response("Unauthorized", status_code=401)
    finally:
        db.close()

    token = _current_user_id.set(user_id)
    try:
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(
                streams[0],
                streams[1],
                server.create_initialization_options(),
            )
    finally:
        _current_user_id.reset(token)
    return _AlreadySentResponse()


async def messages_endpoint(request: Request):
    """Handle MCP JSON-RPC POST messages."""
    await sse.handle_post_message(request.scope, request.receive, request._send)
    return _AlreadySentResponse()
