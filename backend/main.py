from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database.engine import init_db, get_db
from dependencies import verify_token
from routers import weight, dexa, dashboard, coach, nutrition, health_advisor, strava, garmin, profile, hevy
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


# ── Public routes (no JWT required) ─────────────────────────────────────────
app.include_router(auth.router)

# Strava OAuth callback is called by Strava's servers — no JWT available
from fastapi import Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from services.strava_service import StravaService

@app.get("/api/strava/auth/callback", tags=["strava"])
def strava_auth_callback(code: str = Query(...), db: Session = Depends(get_db)):
    svc = StravaService(db)
    token_data = svc.exchange_code(code)
    svc.save_tokens(token_data)
    return RedirectResponse(url=f"{settings.frontend_url}/settings")


# MCP remote server — API key auth (not JWT)
from mcp_server import sse_endpoint, messages_endpoint
app.add_route("/mcp/sse", sse_endpoint)
app.add_route("/mcp/messages", messages_endpoint, methods=["POST"])

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


@app.get("/api/health-check")
def health_check():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/settings/status", dependencies=_auth)
def settings_status():
    return {
        "garmin": bool(settings.garmin_email and settings.garmin_password),
        "hevy": bool(settings.hevy_api_key),
        "anthropic": bool(settings.anthropic_api_key),
        "mcp_api_key": settings.mcp_api_key,
    }
