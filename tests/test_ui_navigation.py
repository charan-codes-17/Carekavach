"""Tests for UI button accessibility and consistent role-aware navigation.

Verifies:
1. "+ Add Medication" is styled as an accessible button with min 48px touch target,
   padding, white text on blue background, and focus ring.
2. Home page (/) displays the exact same role-aware navigation links as the other
   pages (Today, Medications, Appointments, Members, role-aware Audit Log, Sign Out).
"""

import pytest
from httpx import AsyncClient

from app.clock import FixedClock
from app.config import get_settings
from app.dependencies import SESSION_COOKIE_NAME
from app.models import Member, MemberRole, Profile
from app.repositories import MemoryRepository
from app.services.auth import create_session_cookie, hash_passcode


@pytest.fixture
async def setup_nav_members(
    memory_repo: MemoryRepository, fixed_clock: FixedClock
) -> tuple[Member, Member]:
    """Create Profile, Senior, and Family members for navigation checks."""
    profile = Profile(
        id="default_profile",
        senior_name="Grandpa Ramesh",
        timezone="Asia/Kolkata",
        created_at=fixed_clock.now_utc(),
    )
    await memory_repo.create_profile(profile)

    now = fixed_clock.now_utc()
    salt1, hash1 = hash_passcode("pass123")
    senior = Member(
        id="senior_nav",
        profile_id="default_profile",
        name="Ramesh Sharma",
        role=MemberRole.SENIOR,
        can_edit=True,
        passcode_salt=salt1,
        passcode_hash=hash1,
        is_active=True,
        created_at=now,
    )
    await memory_repo.create_member(senior)

    salt2, hash2 = hash_passcode("pass123")
    family = Member(
        id="family_nav",
        profile_id="default_profile",
        name="Asha Sharma",
        role=MemberRole.FAMILY,
        can_edit=False,
        passcode_salt=salt2,
        passcode_hash=hash2,
        is_active=True,
        created_at=now,
    )
    await memory_repo.create_member(family)

    return senior, family


@pytest.mark.asyncio
async def test_add_medication_button_rendered_as_button(
    async_client: AsyncClient,
    fixed_clock: FixedClock,
    setup_nav_members: tuple[Member, Member],
) -> None:
    """'+ Add Medication' link is rendered with button and btn-primary classes."""
    senior, _ = setup_nav_members
    settings = get_settings()

    cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, cookie)

    response = await async_client.get("/medications")
    assert response.status_code == 200
    html = response.text

    # Link has button and btn-primary classes and role="button"
    assert 'class="button btn-primary"' in html
    assert 'role="button"' in html
    assert "+ Add Medication" in html

    # Verify CSS contains the required tokens for min 48px height, padding, white text, focus ring
    css_res = await async_client.get("/static/css/styles.css")
    assert css_res.status_code == 200
    css = css_res.text
    assert "--touch-target-min: 48px;" in css
    assert ".btn-primary" in css
    assert "color: #ffffff" in css
    assert "--color-primary: #1e40af;" in css
    assert "--focus-ring: 3px solid var(--color-focus);" in css


@pytest.mark.asyncio
async def test_home_page_role_aware_navigation_matches_other_pages(
    async_client: AsyncClient,
    fixed_clock: FixedClock,
    setup_nav_members: tuple[Member, Member],
) -> None:
    """Home page navigation includes the same role-aware links as other pages."""
    senior, family = setup_nav_members
    settings = get_settings()

    # 1. Senior view on Home page (/)
    cookie_senior = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, cookie_senior)

    res_home_senior = await async_client.get("/")
    assert res_home_senior.status_code == 200
    html_home_senior = res_home_senior.text

    # Senior must see all nav links on Home page
    assert 'href="/doses/today"' in html_home_senior
    assert 'href="/medications"' in html_home_senior
    assert 'href="/appointments"' in html_home_senior
    assert 'href="/members"' in html_home_senior
    assert 'href="/audit"' in html_home_senior
    assert "Sign Out" in html_home_senior

    # Verify /medications has the same nav links
    res_meds_senior = await async_client.get("/medications")
    assert res_meds_senior.status_code == 200
    html_meds_senior = res_meds_senior.text
    for link in (
        'href="/doses/today"',
        'href="/medications"',
        'href="/appointments"',
        'href="/members"',
        'href="/audit"',
    ):
        assert link in html_meds_senior

    # 2. Family view on Home page (/) — role-aware: Audit Log is hidden
    cookie_family = create_session_cookie(family.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, cookie_family)

    res_home_family = await async_client.get("/")
    assert res_home_family.status_code == 200
    html_home_family = res_home_family.text

    assert 'href="/doses/today"' in html_home_family
    assert 'href="/medications"' in html_home_family
    assert 'href="/appointments"' in html_home_family
    assert 'href="/members"' in html_home_family
    assert 'href="/audit"' not in html_home_family
    assert "Sign Out" in html_home_family
