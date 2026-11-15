from datetime import UTC, datetime, timedelta

from app.clock import FixedClock
from app.services.auth import (
    create_session_cookie,
    decode_session_cookie,
    generate_csrf_token,
    hash_passcode,
    verify_csrf_token,
    verify_dummy_passcode,
    verify_passcode,
)


def test_hash_and_verify_passcode() -> None:
    passcode = "secret123"
    salt, p_hash = hash_passcode(passcode)

    assert len(salt) == 32
    assert len(p_hash) == 64

    # Verification success
    assert verify_passcode(passcode, salt, p_hash) is True

    # Verification failure with wrong passcode
    assert verify_passcode("wrongpass", salt, p_hash) is False


def test_unique_salts_for_identical_passcodes() -> None:
    salt1, hash1 = hash_passcode("same_passcode")
    salt2, hash2 = hash_passcode("same_passcode")

    assert salt1 != salt2
    assert hash1 != hash2


def test_dummy_hash_timing_path() -> None:
    # Always returns False, but exercises identical PBKDF2 path
    assert verify_dummy_passcode("any_input_passcode") is False


def test_session_cookie_lifecycle() -> None:
    base_time = datetime(2026, 11, 15, 10, 0, 0, tzinfo=UTC)
    clock = FixedClock(base_time)
    secret = "test-secret-key-at-least-32-chars-long"

    cookie = create_session_cookie("mem_123", secret, clock, max_age_hours=8)
    assert cookie is not None

    # Valid decode
    decoded = decode_session_cookie(cookie, secret, clock)
    assert decoded == "mem_123"

    # Tampered cookie payload
    parts = cookie.split(":")
    tampered = f"mem_hacked:{parts[1]}:{parts[2]}"
    assert decode_session_cookie(tampered, secret, clock) is None

    # Expired cookie
    clock.set_time(base_time + timedelta(hours=9))
    assert decode_session_cookie(cookie, secret, clock) is None

    # Signature with different secret
    clock.set_time(base_time)
    assert decode_session_cookie(cookie, "different-secret-key", clock) is None


def test_csrf_token_generation_and_verification() -> None:
    session_str = "mem_123:1700000000:abcde"
    secret = "session-secret-key"

    token = generate_csrf_token(session_str, secret)
    assert isinstance(token, str)
    assert len(token) == 64

    assert verify_csrf_token(session_str, token, secret) is True
    assert verify_csrf_token(session_str, "tampered-token", secret) is False
    assert verify_csrf_token("different-session", token, secret) is False
    assert verify_csrf_token("", token, secret) is False
