from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_postgres_scheme(cls, v: str) -> str:
        # Railway (and some other providers) set DATABASE_URL with the legacy
        # "postgres://" scheme. SQLAlchemy 1.4+ requires "postgresql://".
        if isinstance(v, str) and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

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

    # Field-level encryption key (AES-256-GCM).
    # Must be a 64-character hex string (32 bytes).
    # Generate: python -c "import secrets; print(secrets.token_hex(32))"
    field_encryption_key: str = ""

    # Telegram Bot
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""   # e.g. "ai_healthcoachbot" (no @)
    telegram_webhook_secret: str = "" # random string set in setWebhook; validated on every webhook POST

    # Email (Resend)
    resend_api_key: str = ""
    resend_from_email: str = "Health Coach <onboarding@resend.dev>"

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
