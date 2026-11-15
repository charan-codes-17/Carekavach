import pytest
from httpx import AsyncClient

from app.clock import FixedClock
from app.config import get_settings
from app.dependencies import SESSION_COOKIE_NAME
from app.models import Member, MemberRole, Profile
from app.repositories import MemoryRepository
from app.services.auth import create_session_cookie, generate_csrf_token, hash_passcode


@pytest.fixture
async def setup_two_members(
    memory_repo: MemoryRepository, fixed_clock: FixedClock
) -> tuple[Member, Member]:
    """Create senior and caretaker members."""
    profile = Profile(
        id="default_profile",
        senior_name="Grandpa Ramesh",
        timezone="Asia/Kolkata",
        created_at=fixed_clock.now_utc(),
    )
    await memory_repo.create_profile(profile)

    salt1, hash1 = hash_passcode("senior123")
    senior = Member(
        id="senior_1",
        profile_id="default_profile",
        name="Ramesh Sharma",
        email="ramesh.senior@example.com",
        role=MemberRole.SENIOR,
        can_edit=True,
        passcode_salt=salt1,
        passcode_hash=hash1,
        is_active=True,
        created_at=fixed_clock.now_utc(),
    )
    await memory_repo.create_member(senior)

    salt2, hash2 = hash_passcode("caretaker123")
    caretaker = Member(
        id="caretaker_1",
        profile_id="default_profile",
        name="Pooja Sharma",
        email="pooja.caretaker@example.com",
        role=MemberRole.CARETAKER,
        can_edit=True,
        passcode_salt=salt2,
        passcode_hash=hash2,
        is_active=True,
        created_at=fixed_clock.now_utc(),
    )
    await memory_repo.create_member(caretaker)
    return senior, caretaker


@pytest.mark.asyncio
async def test_email_visibility_by_role(
    async_client: AsyncClient,
    fixed_clock: FixedClock,
    setup_two_members: tuple[Member, Member],
) -> None:
    senior, caretaker = setup_two_members
    settings = get_settings()

    # Log in as Caretaker
    caretaker_cookie = create_session_cookie(caretaker.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, caretaker_cookie)

    response = await async_client.get("/members")
    assert response.status_code == 200
    # Caretaker should NOT see emails
    assert "ramesh.senior@example.com" not in response.text
    assert "pooja.caretaker@example.com" not in response.text

    # Log in as Senior
    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)

    response_senior = await async_client.get("/members")
    assert response_senior.status_code == 200
    # Senior DOES see emails
    assert "ramesh.senior@example.com" in response_senior.text
    assert "pooja.caretaker@example.com" in response_senior.text


@pytest.mark.asyncio
async def test_non_senior_cannot_invite_revoke_or_toggle(
    async_client: AsyncClient,
    fixed_clock: FixedClock,
    setup_two_members: tuple[Member, Member],
) -> None:
    _, caretaker = setup_two_members
    settings = get_settings()

    caretaker_cookie = create_session_cookie(caretaker.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, caretaker_cookie)
    csrf_token = generate_csrf_token(caretaker_cookie, settings.SESSION_SECRET)

    # Attempt to invite -> 403 Forbidden
    res_inv = await async_client.post(
        "/members/invite",
        data={
            "name": "New Person",
            "role": "family",
            "passcode": "pass123",
            "csrf_token": csrf_token,
        },
    )
    assert res_inv.status_code == 403

    # Attempt to revoke -> 403 Forbidden
    res_rev = await async_client.post(
        "/members/senior_1/revoke",
        data={"csrf_token": csrf_token},
    )
    assert res_rev.status_code == 403

    # Attempt to toggle can-edit -> 403 Forbidden
    res_tog = await async_client.post(
        "/members/senior_1/can-edit",
        data={"csrf_token": csrf_token},
    )
    assert res_tog.status_code == 403


@pytest.mark.asyncio
async def test_senior_cannot_revoke_themself(
    async_client: AsyncClient,
    fixed_clock: FixedClock,
    setup_two_members: tuple[Member, Member],
) -> None:
    senior, _ = setup_two_members
    settings = get_settings()

    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)
    csrf_token = generate_csrf_token(senior_cookie, settings.SESSION_SECRET)

    # Senior revoking self -> 400 Bad Request
    response = await async_client.post(
        f"/members/{senior.id}/revoke",
        data={"csrf_token": csrf_token},
    )
    assert response.status_code == 400
    assert "Senior cannot revoke their own access" in response.text


@pytest.mark.asyncio
async def test_duplicate_name_case_insensitive_rejected(
    async_client: AsyncClient,
    fixed_clock: FixedClock,
    setup_two_members: tuple[Member, Member],
) -> None:
    senior, _ = setup_two_members
    settings = get_settings()

    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)
    csrf_token = generate_csrf_token(senior_cookie, settings.SESSION_SECRET)

    # Attempt to invite with existing name in different case ("POOJA SHARMA")
    response = await async_client.post(
        "/members/invite",
        data={
            "name": "POOJA SHARMA",
            "role": "family",
            "passcode": "pass123",
            "csrf_token": csrf_token,
        },
    )
    assert response.status_code == 303
    assert "already+exists" in response.headers["location"]


@pytest.mark.asyncio
async def test_revocation_invalidates_existing_cookie_immediately(
    async_client: AsyncClient,
    fixed_clock: FixedClock,
    memory_repo: MemoryRepository,
    setup_two_members: tuple[Member, Member],
) -> None:
    senior, caretaker = setup_two_members
    settings = get_settings()

    caretaker_cookie = create_session_cookie(caretaker.id, settings.SESSION_SECRET, fixed_clock)
    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)

    # Caretaker can currently view members
    async_client.cookies.set(SESSION_COOKIE_NAME, caretaker_cookie)
    res_before = await async_client.get("/members")
    assert res_before.status_code == 200

    # Senior revokes Caretaker
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)
    csrf_token = generate_csrf_token(senior_cookie, settings.SESSION_SECRET)
    res_revoke = await async_client.post(
        f"/members/{caretaker.id}/revoke",
        data={"csrf_token": csrf_token},
    )
    assert res_revoke.status_code == 303

    # Verify Caretaker's active status is False
    updated_caretaker = await memory_repo.get_member_by_id("default_profile", caretaker.id)
    assert updated_caretaker is not None
    assert updated_caretaker.is_active is False

    # Now Caretaker's existing cookie fails on the very next request
    async_client.cookies.set(SESSION_COOKIE_NAME, caretaker_cookie)
    res_after = await async_client.get("/members")
    # Redirects to /login because member is re-read from database on every request
    assert res_after.status_code == 303
    assert res_after.headers["location"] == "/login"

    # Audit entries confirm actions were logged
    audits = await memory_repo.list_audit_entries("default_profile")
    assert any(a.action == "MEMBER_REVOKED" for a in audits)
