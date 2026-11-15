from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.clock import FixedClock
from app.config import get_settings
from app.dependencies import SESSION_COOKIE_NAME
from app.models import Member, MemberRole, Profile
from app.repositories import MemoryRepository
from app.services.auth import create_session_cookie, generate_csrf_token, hash_passcode


@pytest.fixture
async def setup_test_member(memory_repo: MemoryRepository, fixed_clock: FixedClock) -> Member:
    """Seed profile and test senior member."""
    profile = Profile(
        id="default_profile",
        senior_name="Grandpa Ramesh",
        timezone="Asia/Kolkata",
        created_at=fixed_clock.now_utc(),
    )
    await memory_repo.create_profile(profile)

    salt, p_hash = hash_passcode("secret123")
    member = Member(
        id="mem_1",
        profile_id="default_profile",
        name="Ramesh Sharma",
        email="ramesh@example.com",
        role=MemberRole.SENIOR,
        can_edit=True,
        passcode_salt=salt,
        passcode_hash=p_hash,
        is_active=True,
        created_at=fixed_clock.now_utc(),
    )
    return await memory_repo.create_member(member)


@pytest.mark.asyncio
async def test_protected_route_redirects_when_logged_out(async_client: AsyncClient) -> None:
    # Unauthenticated request to / redirects to /login
    response = await async_client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_login_success(
    async_client: AsyncClient,
    setup_test_member: Member,
) -> None:
    response = await async_client.post(
        "/login",
        data={"name": "Ramesh Sharma", "passcode": "secret123"},
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert SESSION_COOKIE_NAME in response.cookies


@pytest.mark.asyncio
async def test_login_generic_error_on_unknown_wrong_or_revoked(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    setup_test_member: Member,
) -> None:
    # Unknown member name
    res1 = await async_client.post(
        "/login", data={"name": "Unknown Person", "passcode": "secret123"}
    )
    assert res1.status_code == 400
    assert "Name or passcode is incorrect" in res1.text

    # Wrong passcode
    res2 = await async_client.post(
        "/login", data={"name": "Ramesh Sharma", "passcode": "wrong_password"}
    )
    assert res2.status_code == 400
    assert "Name or passcode is incorrect" in res2.text

    # Revoked member
    setup_test_member.is_active = False
    await memory_repo.update_member(setup_test_member)
    res3 = await async_client.post(
        "/login", data={"name": "Ramesh Sharma", "passcode": "secret123"}
    )
    assert res3.status_code == 400
    assert "Name or passcode is incorrect" in res3.text


@pytest.mark.asyncio
async def test_login_rate_limiting_and_window_reset(
    async_client: AsyncClient,
    fixed_clock: FixedClock,
    setup_test_member: Member,
) -> None:
    headers = {"X-Forwarded-For": "203.0.113.195"}

    # 5 failed attempts succeed with 400
    for _ in range(5):
        res = await async_client.post(
            "/login",
            data={"name": "Ramesh Sharma", "passcode": "wrongpass"},
            headers=headers,
        )
        assert res.status_code == 400

    # 6th attempt triggers rate limit
    res6 = await async_client.post(
        "/login",
        data={"name": "Ramesh Sharma", "passcode": "wrongpass"},
        headers=headers,
    )
    assert res6.status_code == 429
    assert "Retry-After" in res6.headers

    # Immediate next attempt is also blocked
    res_next = await async_client.post(
        "/login",
        data={"name": "Ramesh Sharma", "passcode": "secret123"},
        headers=headers,
    )
    assert res_next.status_code == 429

    # Advance clock past the 5-minute (300s) sliding window
    current_time = fixed_clock.now_utc()
    fixed_clock.set_time(current_time + timedelta(seconds=305))

    # Now login succeeds
    res_after = await async_client.post(
        "/login",
        data={"name": "Ramesh Sharma", "passcode": "secret123"},
        headers=headers,
    )
    assert res_after.status_code == 303
    assert res_after.headers["location"] == "/"


@pytest.mark.asyncio
async def test_logout_with_csrf_and_missing_csrf_rejected(
    async_client: AsyncClient,
    fixed_clock: FixedClock,
    setup_test_member: Member,
) -> None:
    settings = get_settings()
    session_cookie = create_session_cookie(
        setup_test_member.id,
        settings.SESSION_SECRET,
        fixed_clock,
    )
    async_client.cookies.set(SESSION_COOKIE_NAME, session_cookie)

    # Missing CSRF token -> 403 Forbidden
    res_no_csrf = await async_client.post("/logout", data={})
    assert res_no_csrf.status_code == 403
    assert "Invalid or missing CSRF token" in res_no_csrf.text

    # Valid CSRF token -> Success & Cookie Deleted
    csrf_token = generate_csrf_token(session_cookie, settings.SESSION_SECRET)
    res_logout = await async_client.post("/logout", data={"csrf_token": csrf_token})
    assert res_logout.status_code == 303
    assert res_logout.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_non_ascii_session_cookie_redirects_to_login_not_500(
    async_client: AsyncClient,
) -> None:
    # A non-ASCII cookie should be safely rejected as invalid, cleanly redirecting to /login
    response = await async_client.get(
        "/",
        headers=[(b"cookie", b"carekavach_session=mem_1:1700000000:\xe9signature")],
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_non_ascii_csrf_token_returns_403_not_500(
    async_client: AsyncClient,
    fixed_clock: FixedClock,
    setup_test_member: Member,
) -> None:
    settings = get_settings()
    session_cookie = create_session_cookie(
        setup_test_member.id,
        settings.SESSION_SECRET,
        fixed_clock,
    )
    async_client.cookies.set(SESSION_COOKIE_NAME, session_cookie)

    # Submitting a non-ASCII CSRF token should return 403 Forbidden cleanly, never 500
    response = await async_client.post(
        "/logout",
        data={"csrf_token": "🔥invalid-non-ascii-token"},
    )
    assert response.status_code == 403
    assert "Invalid or missing CSRF token" in response.text
