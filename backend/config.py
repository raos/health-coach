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
    allowed_email: str = ""  # If set, only this Google account can log in

    # Frontend URL (for redirects after OAuth)
    frontend_url: str = "http://localhost:5173"

    # Strava
    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_redirect_uri: str = "http://localhost:8000/api/strava/auth/callback"

    # Garmin
    garmin_email: str = ""
    garmin_password: str = ""

    # Hevy
    hevy_api_key: str = ""
    # Legacy email/password fields kept for backwards compat (unused)
    hevy_email: str = ""
    hevy_password: str = ""

    # MCP remote server API key
    mcp_api_key: str = ""

    # Email (Resend)
    resend_api_key: str = ""  # From resend.com — required for PDF email delivery

    # Database
    database_url: str = "sqlite:///./health.db"

    # Backend
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()
