import hashlib
import hmac
import secrets
from datetime import timedelta

from app.clock import Clock

PBKDF2_ITERATIONS = 200_000
DUMMY_SALT = "00000000000000000000000000000000"
# Pre-computed dummy hash so constant-time dummy verification works uniformly
DUMMY_HASH = hashlib.pbkdf2_hmac(
    "sha256",
    b"dummy-password-for-timing-safety",
    DUMMY_SALT.encode("utf-8"),
    PBKDF2_ITERATIONS,
).hex()


def hash_passcode(passcode: str) -> tuple[str, str]:
    """Generate a random salt and compute PBKDF2-HMAC-SHA256 hash.

    Returns:
        (salt, hash_hex)
    """
    salt = secrets.token_hex(16)
    passcode_hash = hashlib.pbkdf2_hmac(
        "sha256",
        passcode.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return salt, passcode_hash


def verify_passcode(passcode: str, salt: str, expected_hash: str) -> bool:
    """Verify a passcode against salt and expected hash using constant-time comparison."""
    computed_hash = hashlib.pbkdf2_hmac(
        "sha256",
        passcode.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return secrets.compare_digest(computed_hash.encode("utf-8"), expected_hash.encode("utf-8"))


def verify_dummy_passcode(passcode: str) -> bool:
    """Run verification against dummy hash so non-existent users incur identical timing."""
    return verify_passcode(passcode, DUMMY_SALT, DUMMY_HASH)


def create_session_cookie(
    member_id: str,
    session_secret: str,
    clock: Clock,
    max_age_hours: int = 8,
) -> str:
    """Create signed session cookie string: {member_id}:{expiry_timestamp}:{signature}."""
    expiry_time = clock.now_utc() + timedelta(hours=max_age_hours)
    expiry_ts = int(expiry_time.timestamp())
    payload = f"{member_id}:{expiry_ts}"
    signature = hmac.new(
        session_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}:{signature}"


def decode_session_cookie(
    cookie_value: str | None,
    session_secret: str,
    clock: Clock,
) -> str | None:
    """Validate signed session cookie and return member_id if valid and not expired."""
    if not cookie_value:
        return None

    parts = cookie_value.split(":")
    if len(parts) != 3:
        return None

    member_id, expiry_str, signature = parts
    payload = f"{member_id}:{expiry_str}"

    expected_sig = hmac.new(
        session_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not secrets.compare_digest(signature.encode("utf-8"), expected_sig.encode("utf-8")):
        return None

    try:
        expiry_ts = int(expiry_str)
    except ValueError:
        return None

    current_ts = int(clock.now_utc().timestamp())
    if current_ts > expiry_ts:
        return None

    return member_id


def generate_csrf_token(session_str: str, session_secret: str) -> str:
    """Derive an HMAC-SHA256 CSRF token from the session string and secret."""
    return hmac.new(
        session_secret.encode("utf-8"),
        f"csrf:{session_str}".encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_csrf_token(session_str: str, submitted_token: str, session_secret: str) -> bool:
    """Verify submitted CSRF token matches the session-derived token in constant time."""
    if not session_str or not submitted_token:
        return False
    expected = generate_csrf_token(session_str, session_secret)
    return secrets.compare_digest(submitted_token.encode("utf-8"), expected.encode("utf-8"))
