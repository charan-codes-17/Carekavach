from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Security & Sessions
    SESSION_SECRET: str = ""
    SETUP_CODE: str = ""
    SCHEDULER_SECRET: str = ""
    COOKIE_SECURE: bool = False

    @model_validator(mode="after")
    def validate_secrets(self) -> "Settings":
        """Enforce strict secret length and presence rules."""
        if not self.SESSION_SECRET:
            raise ValueError(
                "SESSION_SECRET is required and cannot be empty. "
                "Please configure a secret of at least 32 characters."
            )
        if len(self.SESSION_SECRET) < 32:
            raise ValueError(
                f"SESSION_SECRET must be at least 32 characters long "
                f"(got {len(self.SESSION_SECRET)})."
            )

        if self.SCHEDULER_SECRET and len(self.SCHEDULER_SECRET) < 32:
            raise ValueError(
                f"SCHEDULER_SECRET must be at least 32 characters long when set "
                f"(got {len(self.SCHEDULER_SECRET)})."
            )
        return self

    # Google Cloud & Storage
    GOOGLE_CLOUD_PROJECT: str = ""
    FIREBASE_CREDENTIALS_JSON: str = ""
    USE_FIRESTORE: bool = False

    # AI & Services
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Email
    EMAIL_BACKEND: str = "log"
    EMAIL_FROM: str = "CareKavach <notifications@carekavach.local>"
    RESEND_API_KEY: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # Runtime & Localisation
    PORT: int = 8080
    DEFAULT_TIMEZONE: str = "Asia/Kolkata"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
