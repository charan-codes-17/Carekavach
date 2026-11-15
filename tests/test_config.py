import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.PORT == 8080
    assert settings.DEFAULT_TIMEZONE == "Asia/Kolkata"
    assert settings.GEMINI_MODEL == "gemini-2.5-flash"
    assert settings.USE_FIRESTORE is False
    assert settings.COOKIE_SECURE is False
    assert settings.SETUP_CODE == ""
    assert settings.SMTP_PORT == 587


def test_settings_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "9090")
    monkeypatch.setenv("USE_FIRESTORE", "true")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("SETUP_CODE", "secure-secret-123")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-1.5-pro")
    monkeypatch.setenv("DEFAULT_TIMEZONE", "Asia/Tokyo")

    settings = Settings()
    assert settings.PORT == 9090
    assert settings.USE_FIRESTORE is True
    assert settings.COOKIE_SECURE is True
    assert settings.SETUP_CODE == "secure-secret-123"
    assert settings.GEMINI_MODEL == "gemini-1.5-pro"
    assert settings.DEFAULT_TIMEZONE == "Asia/Tokyo"


def test_settings_empty_session_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "")
    with pytest.raises(ValidationError, match="SESSION_SECRET is required"):
        Settings()


def test_settings_short_session_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "too-short-secret")
    with pytest.raises(ValidationError, match="SESSION_SECRET must be at least 32 characters long"):
        Settings()


def test_settings_valid_session_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "this-is-a-valid-session-secret-with-32-chars")
    s = Settings()
    assert s.SESSION_SECRET == "this-is-a-valid-session-secret-with-32-chars"


def test_settings_short_scheduler_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "this-is-a-valid-session-secret-with-32-chars")
    monkeypatch.setenv("SCHEDULER_SECRET", "short-key")
    with pytest.raises(
        ValidationError, match="SCHEDULER_SECRET must be at least 32 characters long"
    ):
        Settings()


def test_settings_valid_scheduler_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "this-is-a-valid-session-secret-with-32-chars")
    monkeypatch.setenv("SCHEDULER_SECRET", "valid-scheduler-secret-with-over-32-chars")
    s = Settings()
    assert s.SCHEDULER_SECRET == "valid-scheduler-secret-with-over-32-chars"


def test_settings_empty_scheduler_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "this-is-a-valid-session-secret-with-32-chars")
    monkeypatch.setenv("SCHEDULER_SECRET", "")
    s = Settings()
    assert s.SCHEDULER_SECRET == ""
