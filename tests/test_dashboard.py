"""Tests for the role-tailored dashboard (home.html).

Verifies:
1. SENIOR/CARETAKER see the "Next Dose" hero card with Taken/Skip actions posting to
   /doses/log, plus a today's slot list with accessible TEXT status labels.
2. When no slot is pending, the hero card is absent and a plain message is shown.
3. FAMILY sees today's adherence counts and upcoming appointments only, and never any
   private medication.
4. Baseline accessibility: exactly one <h1>, lang attribute, skip link, landmarks.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

from app.clock import FixedClock
from app.config import get_settings
from app.dependencies import SESSION_COOKIE_NAME
from app.models import Appointment, DoseLog, DoseStatus, Medication, Member, MemberRole, Profile
from app.repositories import MemoryRepository
from app.services.auth import create_session_cookie, hash_passcode


def _build_member(
    member_id: str, name: str, role: MemberRole, can_edit: bool, now: datetime
) -> Member:
    salt, passcode_hash = hash_passcode("pass123")
    return Member(
        id=member_id,
        profile_id="default_profile",
        name=name,
        role=role,
        can_edit=can_edit,
        passcode_salt=salt,
        passcode_hash=passcode_hash,
        is_active=True,
        created_at=now,
    )


@pytest.fixture
async def dashboard_env(
    memory_repo: MemoryRepository, fixed_clock: FixedClock
) -> tuple[Member, Member, Member]:
    """Seed one profile, three members, a public + private medication, and one appointment."""
    now = fixed_clock.now_utc()
    profile = Profile(
        id="default_profile",
        senior_name="Grandpa Ramesh",
        timezone="Asia/Kolkata",
        created_at=now,
    )
    await memory_repo.create_profile(profile)

    senior = _build_member("senior_dash", "Ramesh Sharma", MemberRole.SENIOR, True, now)
    caretaker = _build_member("caretaker_dash", "Nurse Latha", MemberRole.CARETAKER, True, now)
    family = _build_member("family_dash", "Asha Sharma", MemberRole.FAMILY, False, now)
    await memory_repo.create_member(senior)
    await memory_repo.create_member(caretaker)
    await memory_repo.create_member(family)

    public_med = Medication(
        id="med_pub",
        profile_id="default_profile",
        name="Metformin",
        dosage="500mg",
        frequency="Twice daily",
        scheduled_times=["09:00", "21:00"],
        is_private=False,
        is_active=True,
        created_by="Ramesh",
        created_at=now,
        updated_at=now,
    )
    private_med = Medication(
        id="med_priv",
        profile_id="default_profile",
        name="Private Cardiac Drug",
        dosage="50mg",
        frequency="Daily",
        scheduled_times=["09:00"],
        is_private=True,
        is_active=True,
        created_by="Ramesh",
        created_at=now,
        updated_at=now,
    )
    await memory_repo.create_medication(public_med)
    await memory_repo.create_medication(private_med)

    appointment = Appointment(
        id="appt_1",
        profile_id="default_profile",
        doctor_name="Dr. Mehta",
        specialty="Cardiology",
        location="City Heart Clinic",
        appointment_datetime=datetime(2026, 11, 20, 4, 30, tzinfo=UTC),
        notes="",
        created_by="Ramesh",
    )
    await memory_repo.create_appointment(appointment)

    return senior, caretaker, family


@pytest.mark.asyncio
async def test_senior_dashboard_shows_next_dose_hero(
    async_client: AsyncClient,
    fixed_clock: FixedClock,
    dashboard_env: tuple[Member, Member, Member],
) -> None:
    """Senior sees the next-dose hero card with Taken/Skip actions and CSRF protection."""
    senior, _, _ = dashboard_env
    settings = get_settings()

    cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, cookie)

    response = await async_client.get("/")
    assert response.status_code == 200
    html = response.text

    # Hero card present with medication name, time, and dosage as typed
    assert "Next Dose" in html
    assert "Metformin" in html
    assert "500mg" in html
    assert "09:00" in html

    # Large Taken / Skip actions posting to /doses/log with CSRF
    assert 'action="/doses/log"' in html
    assert 'name="csrf_token"' in html
    assert 'value="TAKEN"' in html
    assert 'value="SKIPPED"' in html
    assert "Mark as Taken" in html
    assert "Skip Dose" in html

    # Today's slot list uses text status labels (never colour alone)
    assert "Status:" in html
    assert "Pending" in html or "Due at" in html or "Scheduled for" in html

    # Accessibility baseline
    assert html.count("<h1") == 1
    assert 'lang="en"' in html
    assert "Skip to main content" in html
    assert 'role="main"' in html


@pytest.mark.asyncio
async def test_caretaker_dashboard_shows_next_dose_hero(
    async_client: AsyncClient,
    fixed_clock: FixedClock,
    dashboard_env: tuple[Member, Member, Member],
) -> None:
    """Caretaker also sees the next-dose hero card (SENIOR/CARETAKER share this dashboard)."""
    _, caretaker, _ = dashboard_env
    settings = get_settings()

    cookie = create_session_cookie(caretaker.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, cookie)

    response = await async_client.get("/")
    assert response.status_code == 200
    assert "Next Dose" in response.text


@pytest.mark.asyncio
async def test_hero_card_absent_when_nothing_pending(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    dashboard_env: tuple[Member, Member, Member],
) -> None:
    """When every slot is already logged, the hero card is absent and a plain message is shown."""
    senior, _, _ = dashboard_env
    settings = get_settings()
    now = fixed_clock.now_utc()
    tz = ZoneInfo("Asia/Kolkata")
    today_str = now.astimezone(tz).strftime("%Y-%m-%d")

    for med_id, med_name, slot_time in (
        ("med_pub", "Metformin", "09:00"),
        ("med_pub", "Metformin", "21:00"),
        ("med_priv", "Private Cardiac Drug", "09:00"),
    ):
        await memory_repo.create_dose_log(
            DoseLog(
                id=f"{med_id}_{today_str}_{slot_time}",
                profile_id="default_profile",
                medication_id=med_id,
                medication_name=med_name,
                scheduled_date=today_str,
                scheduled_time=slot_time,
                status=DoseStatus.TAKEN,
                logged_by_member_id=senior.id,
                logged_by_name=senior.name,
                logged_at=now,
            )
        )

    cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, cookie)

    response = await async_client.get("/")
    assert response.status_code == 200
    html = response.text

    assert "Next Dose" not in html
    assert "Nothing is due" in html


@pytest.mark.asyncio
async def test_family_dashboard_hides_private_medications(
    async_client: AsyncClient,
    fixed_clock: FixedClock,
    dashboard_env: tuple[Member, Member, Member],
) -> None:
    """FAMILY sees adherence counts and upcoming appointments, and never a private medication."""
    _, _, family = dashboard_env
    settings = get_settings()

    cookie = create_session_cookie(family.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, cookie)

    response = await async_client.get("/")
    assert response.status_code == 200
    html = response.text

    # Private medication never leaks anywhere on the family dashboard
    assert "Private Cardiac Drug" not in html

    # Today's adherence counts are shown
    assert "Doses taken:" in html
    assert "Doses skipped:" in html
    assert "Doses missed:" in html
    assert "Doses still pending:" in html

    # Upcoming appointments are shown
    assert "Upcoming Doctor Appointments" in html
    assert "Dr. Mehta" in html
    assert "Cardiology" in html

    # No next-dose hero actions for a read-only family member
    assert "Next Dose" not in html
    assert 'action="/doses/log"' not in html

    # Accessibility baseline
    assert html.count("<h1") == 1
    assert "Skip to main content" in html
