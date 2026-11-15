"""Tests for proxy-aware IP extraction and /health with empty optional settings.

These tests confirm the app behaves correctly behind Render's reverse-proxy
(X-Forwarded-For header) and when SMTP / Gemini env vars are absent.
"""

from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient

from app.services.rate_limiter import extract_client_ip

# ---------------------------------------------------------------------------
# X-Forwarded-For extraction
# ---------------------------------------------------------------------------


def _make_request(xff: str | None = None, client_host: str | None = "10.0.0.1") -> MagicMock:
    """Build a minimal mock Request with the given X-Forwarded-For header."""
    req = MagicMock()
    req.headers = {}
    if xff is not None:
        req.headers = {"x-forwarded-for": xff}
    if client_host is not None:
        req.client = MagicMock()
        req.client.host = client_host
    else:
        req.client = None
    return req


def test_extract_client_ip_single_xff() -> None:
    """Single IP in X-Forwarded-For is returned directly."""
    req = _make_request(xff="203.0.113.42")
    assert extract_client_ip(req) == "203.0.113.42"


def test_extract_client_ip_first_of_many_xff() -> None:
    """First value in a comma-separated X-Forwarded-For chain is the client IP."""
    req = _make_request(xff="203.0.113.42, 10.1.2.3, 172.16.0.1")
    assert extract_client_ip(req) == "203.0.113.42"


def test_extract_client_ip_xff_with_spaces() -> None:
    """Leading/trailing spaces around each IP in X-Forwarded-For are stripped."""
    req = _make_request(xff="  198.51.100.7 , 10.0.0.2")
    assert extract_client_ip(req) == "198.51.100.7"


def test_extract_client_ip_no_xff_falls_back_to_client_host() -> None:
    """Without X-Forwarded-For, the ASGI client host is used."""
    req = _make_request(xff=None, client_host="192.168.1.50")
    assert extract_client_ip(req) == "192.168.1.50"


def test_extract_client_ip_no_xff_no_client_returns_loopback() -> None:
    """Without any IP source, returns localhost sentinel."""
    req = _make_request(xff=None, client_host=None)
    assert extract_client_ip(req) == "127.0.0.1"


def test_extract_client_ip_empty_xff_falls_back_to_client_host() -> None:
    """An empty X-Forwarded-For header falls back to client.host."""
    req = _make_request(xff="", client_host="10.10.10.10")
    # An empty string split gives [""], which strips to "" — falsy, so we fall through
    assert extract_client_ip(req) == "10.10.10.10"


# ---------------------------------------------------------------------------
# /health works with empty optional settings (SMTP, Gemini)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_ok_with_empty_optional_settings(async_client: AsyncClient) -> None:
    """/health returns 200 even when SMTP and Gemini vars are unset."""
    res = await async_client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "healthy"
    assert body["service"] == "carekavach"


@pytest.mark.asyncio
async def test_health_db_ok_with_memory_repo(async_client: AsyncClient) -> None:
    """/health/db returns 200 for in-memory repository (no Firestore credentials needed)."""
    res = await async_client.get("/health/db")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "healthy"
    assert body["database"] == "memory"
