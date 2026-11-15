from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Security & Sessions
    SESSION_SECRET: str = "dev-insecure-session-secret-at-least-32-chars"
    SETUP_CODE: str = ""
    SCHEDULER_SECRET: str = ""
    COOKIE_SECURE: bool = False

    # Google Cloud & Storage
    GOOGLE_CLOUD_PROJECT: str = ""
    FIREBASE_CREDENTIALS_JSON: str = ""
    USE_FIRESTORE: bool = False

    # AI & Services
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Email
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
