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

    # Email (SMTP)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""   # Gmail App Password (16 chars, no spaces)
    email_from: str = ""      # Defaults to smtp_user if blank
    email_recipients_training_plan: str = ""  # Comma-separated; training plan PDF recipients
    email_recipients_meal_plan: str = ""      # Comma-separated; meal plan PDF recipients

    @property
    def training_plan_recipients(self) -> List[str]:
        return [e.strip() for e in self.email_recipients_training_plan.split(",") if e.strip()]

    @property
    def meal_plan_recipients(self) -> List[str]:
        return [e.strip() for e in self.email_recipients_meal_plan.split(",") if e.strip()]

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
