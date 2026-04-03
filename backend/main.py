from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database.engine import init_db, get_db
from dependencies import verify_token
from routers import weight, dexa, dashboard, coach, nutrition, health_advisor, strava, garmin, profile, hevy, supplements, checkin, email
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
from starlette.requests import Request
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

# ── Protected routes (JWT required) ─────────────────────────────────────────
_auth = [Depends(verify_token)]
app.include_router(weight.router, dependencies=_auth)
app.include_router(dexa.router, dependencies=_auth)
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


@app.get("/api/health-check")
def health_check():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/settings/status", dependencies=_auth)
def settings_status(
    request: Request,
    db: Session = Depends(get_db),
):
    from dependencies import get_user_id as _get_uid
    from database.models import UserProfile as _UP
    import uuid as _uuid
    # Try to get per-user MCP key; fall back to global
    try:
        token_data = verify_token(request.headers.get("Authorization", "").removeprefix("Bearer "))
        uid = _uuid.UUID(token_data["user_id"]) if token_data.get("user_id") else None
        profile = db.query(_UP).filter(_UP.user_id == uid).first() if uid else None
        mcp_key = (profile.mcp_api_key if profile and profile.mcp_api_key else None) or settings.mcp_api_key
        hevy_configured = bool((profile.hevy_api_key if profile else None) or settings.hevy_api_key)
    except Exception:
        mcp_key = settings.mcp_api_key
        hevy_configured = bool(settings.hevy_api_key)
    return {
        "garmin": bool(settings.garmin_email and settings.garmin_password),
        "hevy": hevy_configured,
        "anthropic": bool(settings.anthropic_api_key),
        "mcp_api_key": mcp_key,
    }
