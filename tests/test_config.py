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


def test_settings_overrides(monkeypatch: object) -> None:
    # Use monkeypatch fixture from pytest
    from pytest import MonkeyPatch

    mp = MonkeyPatch()
    mp.setenv("PORT", "9090")
    mp.setenv("USE_FIRESTORE", "true")
    mp.setenv("COOKIE_SECURE", "true")
    mp.setenv("SETUP_CODE", "secure-secret-123")
    mp.setenv("GEMINI_MODEL", "gemini-1.5-pro")
    mp.setenv("DEFAULT_TIMEZONE", "Asia/Tokyo")

    settings = Settings()
    assert settings.PORT == 9090
    assert settings.USE_FIRESTORE is True
    assert settings.COOKIE_SECURE is True
    assert settings.SETUP_CODE == "secure-secret-123"
    assert settings.GEMINI_MODEL == "gemini-1.5-pro"
    assert settings.DEFAULT_TIMEZONE == "Asia/Tokyo"
    mp.undo()
