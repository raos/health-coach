import uuid
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database.engine import init_db, get_db
from dependencies import verify_token, get_user_id
from routers import weight, body_composition, dashboard, coach, nutrition, health_advisor, strava, garmin, profile, hevy, supplements, checkin, email, admin, account, telegram
from routers import auth

app = FastAPI(
    title="Health Coach API",
    description="Personal health coaching, nutrition, and fitness tracking",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    init_db()
    _start_scheduler()


def _start_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from services.weekly_summary_service import send_weekly_summary_all_users
    import logging

    scheduler = BackgroundScheduler(timezone="America/New_York")
    scheduler.add_job(
        send_weekly_summary_all_users,
        CronTrigger(day_of_week="sun", hour=19, minute=30, timezone="America/New_York"),
        id="weekly_summary",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logging.getLogger(__name__).info("Scheduler started — weekly summary fires every Sunday 7:30 PM ET")


# ── Public routes (no JWT required) ─────────────────────────────────────────
app.include_router(auth.router)

# Strava OAuth callback is called by Strava's servers — no JWT available
from fastapi import Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from services.strava_service import StravaService

@app.get("/api/strava/auth/callback", tags=["strava"])
def strava_auth_callback(
    code: str = Query(...),
    state: str = Query(default=""),
    db: Session = Depends(get_db),
):
    import uuid as _uuid
    user_id = None
    if state:
        try:
            user_id = _uuid.UUID(state)
        except ValueError:
            pass
    svc = StravaService(db, user_id)
    token_data = svc.exchange_code(code)
    svc.save_tokens(token_data)
    return RedirectResponse(url=f"{settings.frontend_url}/settings")


# MCP remote server — API key auth (not JWT)
from mcp_server import sse_endpoint, messages_endpoint
app.add_route("/mcp/sse", sse_endpoint)
app.add_route("/mcp/messages", messages_endpoint, methods=["POST"])

# Garmin push-data — API key auth (not JWT), called from local sync script
from routers.garmin import push_data as garmin_push_data
app.add_api_route("/api/garmin/push-data", garmin_push_data, methods=["POST"], tags=["garmin"])

# Telegram webhook — called by Telegram's servers, no JWT
app.include_router(telegram.router)

# ── Protected routes (JWT required) ─────────────────────────────────────────
_auth = [Depends(verify_token)]
app.include_router(weight.router, dependencies=_auth)
app.include_router(body_composition.router, dependencies=_auth)
app.include_router(dashboard.router, dependencies=_auth)
app.include_router(coach.router, dependencies=_auth)
app.include_router(nutrition.router, dependencies=_auth)
app.include_router(health_advisor.router, dependencies=_auth)
app.include_router(strava.router, dependencies=_auth)
app.include_router(garmin.router, dependencies=_auth)
app.include_router(profile.router, dependencies=_auth)
app.include_router(hevy.router, dependencies=_auth)
app.include_router(supplements.router, dependencies=_auth)
app.include_router(checkin.router, dependencies=_auth)
app.include_router(email.router, dependencies=_auth)
app.include_router(admin.router, dependencies=_auth)
app.include_router(account.router, dependencies=_auth)


@app.get("/api/health-check")
def health_check():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/settings/status", dependencies=_auth)
def settings_status(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    from database.models import UserProfile as _UP
    profile = db.query(_UP).filter(_UP.user_id == user_id).first()
    # Auto-generate MCP key for existing users who don't have one yet
    if profile and not profile.mcp_api_key:
        profile.mcp_api_key = str(uuid.uuid4())
        db.commit()
    return {
        "hevy": bool(profile.hevy_api_key if profile else None),
        "anthropic": bool(settings.anthropic_api_key),
        "mcp_api_key": profile.mcp_api_key if profile else None,
        "telegram_connected": bool(profile.telegram_chat_id if profile else None),
        "telegram_bot_username": settings.telegram_bot_username,
    }
