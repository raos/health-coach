from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Claude AI
    anthropic_api_key: str = ""

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    # JWT
    jwt_secret_key: str = "change-this-to-a-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 30

    # Multi-tenant: admin email gets is_admin=True on first login
    admin_email: str = ""
    # Legacy single-user gate (ignored in multi-tenant mode, kept for compat)
    allowed_email: str = ""

    # Frontend URL (for redirects after OAuth)
    frontend_url: str = "http://localhost:5173"

    # Strava
    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_redirect_uri: str = "http://localhost:8000/api/strava/auth/callback"

    # MCP remote server — global fallback key for /api/garmin/push-data backwards compat.
    # Per-user keys are stored in UserProfile.mcp_api_key and are the primary auth mechanism.
    mcp_api_key: str = ""

    # Email (Resend)
    resend_api_key: str = ""
    resend_from_email: str = "HealthCoach <onboarding@resend.dev>"

    # Database — defaults to local Postgres for multi-tenant branch
    database_url: str = "postgresql://localhost/health_coach_dev"

    # Backend
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()
