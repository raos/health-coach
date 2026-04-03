"""
Weekly summary email — gathers last 7 days of data and sends an HTML digest.
"""
import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy.orm import Session

from database.engine import SessionLocal
from database.models import (
    DailyHealthCache,
    HevyWorkout,
    NutritionLog,
    User,
    UserProfile,
    WeightLog,
)
from services.email_service import send_html_email

# Backward compat alias
GarminDailyCache = DailyHealthCache


# ── Helpers ──────────────────────────────────────────────────────────────────

def _avg(values: list) -> float | None:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 1)


def _fmt_weight(w: float | None) -> str:
    return f"{w:.1f} lbs" if w is not None else "—"


def _fmt_steps(s: float | None) -> str:
    return f"{int(s):,}" if s is not None else "—"


def _trend(current: float | None, previous: float | None) -> str:
    if current is None or previous is None:
        return ""
    diff = round(current - previous, 1)
    if abs(diff) < 0.05:
        return "<span style='color:#6b7280'>→ unchanged</span>"
    color = "#16a34a" if diff < 0 else "#dc2626"
    arrow = "↓" if diff < 0 else "↑"
    return f"<span style='color:{color}'>{arrow} {abs(diff):.1f} vs prev week</span>"


# ── Data gathering ────────────────────────────────────────────────────────────

def _gather(db: Session, user_id: uuid.UUID) -> dict:
    today = date.today()
    week_start = today - timedelta(days=6)
    prev_start = today - timedelta(days=13)

    # Weight
    weight_rows = (
        db.query(WeightLog)
        .filter(WeightLog.user_id == user_id, WeightLog.date >= week_start)
        .order_by(WeightLog.date)
        .all()
    )
    prev_weight = (
        db.query(WeightLog)
        .filter(WeightLog.user_id == user_id, WeightLog.date >= prev_start, WeightLog.date < week_start)
        .all()
    )
    avg_w = _avg([r.weight_lbs for r in weight_rows])
    prev_avg_w = _avg([r.weight_lbs for r in prev_weight])

    # Workouts
    workouts = (
        db.query(HevyWorkout)
        .filter(HevyWorkout.user_id == user_id, HevyWorkout.start_time >= week_start)
        .order_by(HevyWorkout.start_time)
        .all()
    )

    # Nutrition
    nutrition = (
        db.query(NutritionLog)
        .filter(NutritionLog.user_id == user_id, NutritionLog.date >= week_start)
        .all()
    )
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    calorie_target = profile.calorie_target if profile else 2200

    daily_kcal: dict[date, int] = defaultdict(int)
    daily_protein: dict[date, float] = defaultdict(float)
    for row in nutrition:
        daily_kcal[row.date] += row.kcal
        daily_protein[row.date] += row.protein_g

    # Health cache (Garmin / Google Fit)
    health_rows = (
        db.query(DailyHealthCache)
        .filter(DailyHealthCache.user_id == user_id, DailyHealthCache.date >= week_start)
        .order_by(DailyHealthCache.date)
        .all()
    )

    return {
        "today": today,
        "week_start": week_start,
        "weight": {
            "entries": [(r.date, r.weight_lbs) for r in weight_rows],
            "avg": avg_w,
            "prev_avg": prev_avg_w,
        },
        "workouts": workouts,
        "nutrition": {
            "days_logged": len(daily_kcal),
            "avg_kcal": _avg(list(daily_kcal.values())),
            "avg_protein": _avg(list(daily_protein.values())),
            "calorie_target": calorie_target,
        },
        "garmin": {
            "avg_steps": _avg([r.steps for r in health_rows]),
            "avg_sleep": _avg([r.sleep_duration_hours for r in health_rows]),
            "avg_rhr": _avg([r.resting_hr for r in health_rows]),
        },
    }


# ── HTML email builder ────────────────────────────────────────────────────────

def _section(title: str, rows: list[tuple[str, str]]) -> str:
    """Render a named section as an HTML table of label/value rows."""
    row_html = "".join(
        f"""
        <tr>
          <td style="padding:6px 12px 6px 0;color:#6b7280;font-size:14px;white-space:nowrap">{label}</td>
          <td style="padding:6px 0;font-size:14px;font-weight:600;color:#111827">{value}</td>
        </tr>"""
        for label, value in rows
    )
    return f"""
    <div style="margin-bottom:28px">
      <div style="font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;
                  color:#4f46e5;border-bottom:2px solid #e5e7eb;padding-bottom:6px;margin-bottom:12px">
        {title}
      </div>
      <table style="border-collapse:collapse;width:100%"><tbody>{row_html}</tbody></table>
    </div>"""


def _build_html(data: dict) -> str:
    week_str = data["week_start"].strftime("%b %d") + " – " + data["today"].strftime("%b %d, %Y")

    # Weight section
    w = data["weight"]
    weight_rows: list[tuple[str, str]] = []
    for d, lbs in w["entries"]:
        weight_rows.append((d.strftime("%a %b %d"), f"{lbs:.1f} lbs"))
    if not weight_rows:
        weight_rows.append(("", "No entries this week"))
    if w["avg"] is not None:
        weight_rows.append(("7-day avg", f"{_fmt_weight(w['avg'])} &nbsp; {_trend(w['avg'], w['prev_avg'])}"))

    # Workouts section
    wo = data["workouts"]
    if wo:
        workout_rows = [
            (
                w.start_time.strftime("%a %b %d"),
                f"{w.title} &nbsp;<span style='color:#6b7280;font-weight:400'>({int((w.duration_s or 0)/60)} min)</span>",
            )
            for w in wo
        ]
    else:
        workout_rows = [("", "No workouts logged this week")]

    # Nutrition section
    n = data["nutrition"]
    compliance = (
        f"{round(n['avg_kcal'] / n['calorie_target'] * 100)}%"
        if n["avg_kcal"] and n["calorie_target"]
        else "—"
    )
    nutrition_rows = [
        ("Days logged", f"{n['days_logged']} / 7"),
        ("Avg calories", f"{int(n['avg_kcal']):,} kcal &nbsp;<span style='color:#6b7280;font-weight:400'>({compliance} of {n['calorie_target']:,} target)</span>" if n["avg_kcal"] else "—"),
        ("Avg protein", f"{int(n['avg_protein'])} g" if n["avg_protein"] else "—"),
    ]

    # Garmin section
    g = data["garmin"]
    step_note = ""
    if g["avg_steps"]:
        pct = round(g["avg_steps"] / 10000 * 100)
        color = "#16a34a" if pct >= 80 else "#d97706"
        step_note = f" &nbsp;<span style='color:{color};font-weight:400'>({pct}% of 10k goal)</span>"

    sleep_note = ""
    if g["avg_sleep"]:
        color = "#16a34a" if g["avg_sleep"] >= 7 else "#d97706"
        sleep_note = f" &nbsp;<span style='color:{color};font-weight:400'>({'✓' if g['avg_sleep'] >= 7.5 else 'below 7.5h goal'})</span>"

    garmin_rows = [
        ("Avg daily steps", f"{_fmt_steps(g['avg_steps'])}{step_note}"),
        ("Avg sleep", f"{g['avg_sleep']}h{sleep_note}" if g["avg_sleep"] else "—"),
        ("Avg resting HR", f"{int(g['avg_rhr'])} bpm" if g["avg_rhr"] else "—"),
    ]

    body = (
        _section("⚖️ Weight", weight_rows)
        + _section("🏋️ Workouts", workout_rows)
        + _section("🥗 Nutrition", nutrition_rows)
        + _section("⌚ Health Highlights", garmin_rows)
    )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:32px 16px">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;
             box-shadow:0 1px 3px rgba(0,0,0,.1);overflow:hidden;max-width:600px">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);padding:28px 32px">
            <div style="font-size:22px;font-weight:700;color:#ffffff">Weekly Health Summary</div>
            <div style="font-size:14px;color:#c7d2fe;margin-top:4px">{week_str}</div>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:28px 32px">
            {body}
            <div style="margin-top:24px;padding-top:16px;border-top:1px solid #e5e7eb;
                        font-size:12px;color:#9ca3af;text-align:center">
              Health Coach &nbsp;·&nbsp; Generated automatically every Sunday at 7:30 PM
            </div>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


# ── Public entry points ───────────────────────────────────────────────────────

def send_weekly_summary_for_user(user_id: uuid.UUID, db: Session) -> None:
    """Send the weekly summary for a specific user. Called by the email router and the scheduler."""
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    user = db.query(User).filter(User.id == user_id).first()
    recipient = (profile.email if profile and getattr(profile, "email", None) else None) or (user.email if user else None)
    if not recipient:
        raise RuntimeError(f"No email address found for user {user_id}.")

    # Respect opt-out
    if profile and not getattr(profile, "weekly_email_enabled", True):
        return

    data = _gather(db, user_id)
    html = _build_html(data)
    week_str = data["week_start"].strftime("%b %d") + " – " + data["today"].strftime("%b %d")
    cc = getattr(profile, "weekly_email_cc", None) if profile else None
    send_html_email(
        to_address=recipient,
        subject=f"Weekly Health Summary — {week_str}",
        html=html,
        cc=cc,
    )


def send_weekly_summary_all_users() -> None:
    """Loop over all active users with email enabled and send their summaries. Called by the scheduler."""
    import logging
    log = logging.getLogger(__name__)
    db = SessionLocal()
    try:
        profiles = (
            db.query(UserProfile)
            .filter(UserProfile.weekly_email_enabled == True)
            .all()
        )
        for profile in profiles:
            if not profile.user_id:
                continue
            try:
                send_weekly_summary_for_user(user_id=profile.user_id, db=db)
                log.info("Weekly summary sent for user %s", profile.user_id)
            except Exception as exc:
                log.error("Failed to send weekly summary for user %s: %s", profile.user_id, exc)
    finally:
        db.close()


# Legacy shim — kept so any old direct callers don't break
def send_weekly_summary() -> None:
    """Deprecated: use send_weekly_summary_all_users() instead."""
    send_weekly_summary_all_users()
