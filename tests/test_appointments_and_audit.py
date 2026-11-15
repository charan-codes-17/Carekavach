from datetime import UTC, timedelta

import pytest
from httpx import AsyncClient

from app.clock import FixedClock
from app.config import get_settings
from app.dependencies import SESSION_COOKIE_NAME
from app.models import Appointment, Member, MemberRole, Profile
from app.repositories import MemoryRepository
from app.services.auth import create_session_cookie, generate_csrf_token, hash_passcode


@pytest.fixture
async def setup_appointment_members(
    memory_repo: MemoryRepository, fixed_clock: FixedClock
) -> tuple[Member, Member, Member]:
    """Create Profile, Senior, Caretaker, and Family members."""
    profile = Profile(
        id="default_profile",
        senior_name="Grandpa Ramesh",
        timezone="Asia/Kolkata",
        created_at=fixed_clock.now_utc(),
    )
    await memory_repo.create_profile(profile)

    salt1, hash1 = hash_passcode("pass123")
    senior = Member(
        id="senior_1",
        profile_id="default_profile",
        name="Ramesh Sharma",
        role=MemberRole.SENIOR,
        can_edit=True,
        passcode_salt=salt1,
        passcode_hash=hash1,
        is_active=True,
        created_at=fixed_clock.now_utc(),
    )
    await memory_repo.create_member(senior)

    salt2, hash2 = hash_passcode("pass123")
    caretaker = Member(
        id="caretaker_1",
        profile_id="default_profile",
        name="Pooja Sharma",
        role=MemberRole.CARETAKER,
        can_edit=True,
        passcode_salt=salt2,
        passcode_hash=hash2,
        is_active=True,
        created_at=fixed_clock.now_utc(),
    )
    await memory_repo.create_member(caretaker)

    salt3, hash3 = hash_passcode("pass123")
    family = Member(
        id="family_1",
        profile_id="default_profile",
        name="Asha Sharma",
        role=MemberRole.FAMILY,
        can_edit=False,
        passcode_salt=salt3,
        passcode_hash=hash3,
        is_active=True,
        created_at=fixed_clock.now_utc(),
    )
    await memory_repo.create_member(family)

    return senior, caretaker, family


@pytest.mark.asyncio
async def test_appointment_scheduling_and_past_rejection(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    setup_appointment_members: tuple[Member, Member, Member],
) -> None:
    senior, _, _ = setup_appointment_members
    settings = get_settings()

    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)
    csrf_token = generate_csrf_token(senior_cookie, settings.SESSION_SECRET)

    # 1. Past appointment rejected
    res_past = await async_client.post(
        "/appointments",
        data={
            "csrf_token": csrf_token,
            "doctor_name": "Dr. Past",
            "specialty": "General",
            "location": "City Clinic",
            "appointment_datetime": "2026-11-14T10:00",  # Yesterday
        },
    )
    assert res_past.status_code == 400
    assert "must be in the future" in res_past.text

    # 2. Future appointment scheduled
    res_future = await async_client.post(
        "/appointments",
        data={
            "csrf_token": csrf_token,
            "doctor_name": "Dr. Mehta",
            "specialty": "Cardiologist",
            "location": "Apollo Hospital",
            "appointment_datetime": "2026-11-20T10:30",
            "notes": "Bring ECG",
        },
    )
    assert res_future.status_code == 303

    appts = await memory_repo.list_appointments("default_profile")
    assert len(appts) == 1
    assert appts[0].doctor_name == "Dr. Mehta"
    # Stored in UTC: 2026-11-20 10:30 IST is 05:00 UTC (IST = UTC+5:30)
    assert appts[0].appointment_datetime.tzinfo == UTC
    assert appts[0].appointment_datetime.hour == 5
    assert appts[0].appointment_datetime.minute == 0


@pytest.mark.asyncio
async def test_appointments_sorted_and_past_ones_hidden(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    setup_appointment_members: tuple[Member, Member, Member],
) -> None:
    senior, _, _ = setup_appointment_members
    settings = get_settings()

    # Pre-seed appointments: 1 past, 2 future (out of order)
    now = fixed_clock.now_utc()
    past_appt = Appointment(
        id="appt_past",
        profile_id="default_profile",
        doctor_name="Dr. Old",
        specialty="General",
        location="Clinic",
        appointment_datetime=now - timedelta(days=2),
        created_by="Senior",
    )
    future_appt2 = Appointment(
        id="appt_f2",
        profile_id="default_profile",
        doctor_name="Dr. Later",
        specialty="Dentist",
        location="Dental Clinic",
        appointment_datetime=now + timedelta(days=5),
        created_by="Senior",
    )
    future_appt1 = Appointment(
        id="appt_f1",
        profile_id="default_profile",
        doctor_name="Dr. Sooner",
        specialty="Eye Care",
        location="Vision Center",
        appointment_datetime=now + timedelta(days=2),
        created_by="Senior",
    )
    await memory_repo.create_appointment(past_appt)
    await memory_repo.create_appointment(future_appt2)
    await memory_repo.create_appointment(future_appt1)

    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)

    res = await async_client.get("/appointments")
    assert res.status_code == 200
    html = res.text

    # Past appointment is hidden
    assert "Dr. Old" not in html
    # Future ones are displayed
    assert "Dr. Sooner" in html
    assert "Dr. Later" in html
    # Chronological order: Sooner appears before Later in HTML
    pos_sooner = html.find("Dr. Sooner")
    pos_later = html.find("Dr. Later")
    assert pos_sooner < pos_later


@pytest.mark.asyncio
async def test_audit_log_role_gating_and_no_secrets(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    setup_appointment_members: tuple[Member, Member, Member],
) -> None:
    senior, caretaker, family = setup_appointment_members
    settings = get_settings()

    # 1. Family cannot view audit log -> 403 Forbidden
    family_cookie = create_session_cookie(family.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, family_cookie)
    res_fam = await async_client.get("/audit")
    assert res_fam.status_code == 403

    # 2. Caretaker can view audit log -> 200 OK
    caretaker_cookie = create_session_cookie(caretaker.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, caretaker_cookie)
    res_care = await async_client.get("/audit")
    assert res_care.status_code == 200

    # 3. Senior can view audit log -> 200 OK
    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)
    res_sen = await async_client.get("/audit")
    assert res_sen.status_code == 200

    # Verify no passcodes or secret hashes are in audit output
    assert "secret123" not in res_sen.text
    assert "pass123" not in res_sen.text
    assert senior.passcode_hash not in res_sen.text
    assert caretaker.passcode_hash not in res_sen.text


@pytest.mark.asyncio
async def test_csrf_missing_rejected_on_appointment_create(
    async_client: AsyncClient,
    fixed_clock: FixedClock,
    setup_appointment_members: tuple[Member, Member, Member],
) -> None:
    senior, _, _ = setup_appointment_members
    settings = get_settings()

    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)

    # Missing CSRF on appointment POST -> 403
    res = await async_client.post(
        "/appointments",
        data={
            "doctor_name": "Dr. Verma",
            "specialty": "Dentist",
            "location": "Smile Clinic",
            "appointment_datetime": "2026-11-20T10:00",
        },
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_appointment_stored_in_utc_and_displayed_in_ist(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    setup_appointment_members: tuple[Member, Member, Member],
) -> None:
    senior, _, _ = setup_appointment_members
    settings = get_settings()

    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)
    csrf_token = generate_csrf_token(senior_cookie, settings.SESSION_SECRET)

    # 15:30 IST on Nov 25, 2026
    res = await async_client.post(
        "/appointments",
        data={
            "csrf_token": csrf_token,
            "doctor_name": "Dr. Roy",
            "specialty": "Neurology",
            "location": "Metro Hospital",
            "appointment_datetime": "2026-11-25T15:30",
        },
    )
    assert res.status_code == 303

    appts = await memory_repo.list_appointments("default_profile")
    roy_appts = [a for a in appts if a.doctor_name == "Dr. Roy"]
    assert len(roy_appts) == 1
    appt = roy_appts[0]

    # Stored in UTC: 15:30 IST is 10:00 UTC
    assert appt.appointment_datetime.tzinfo == UTC
    assert appt.appointment_datetime.hour == 10
    assert appt.appointment_datetime.minute == 0

    # Displayed in IST on GET /appointments: 3:30 PM
    res_get = await async_client.get("/appointments")
    assert res_get.status_code == 200
    assert "Wed, 25 Nov 2026 at 3:30 PM" in res_get.text


@pytest.mark.asyncio
async def test_audit_trail_captures_all_events_without_secrets(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    setup_appointment_members: tuple[Member, Member, Member],
) -> None:
    senior, _, _ = setup_appointment_members
    settings = get_settings()

    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)
    csrf_token = generate_csrf_token(senior_cookie, settings.SESSION_SECRET)

    # 1. Medication create
    await async_client.post(
        "/medications",
        data={
            "csrf_token": csrf_token,
            "name": "Audit Test Pill",
            "dosage": "20mg",
            "frequency": "Daily",
            "scheduled_times": "08:00",
        },
    )
    meds = await memory_repo.list_medications("default_profile")
    med = [m for m in meds if m.name == "Audit Test Pill"][0]

    # 2. Medication edit
    await async_client.post(
        f"/medications/{med.id}/edit",
        data={
            "csrf_token": csrf_token,
            "name": "Audit Test Pill Extra",
            "dosage": "30mg",
            "frequency": "Daily",
            "scheduled_times": "08:00",
        },
    )

    # 3. Dose log
    await async_client.post(
        "/doses/log",
        data={
            "csrf_token": csrf_token,
            "medication_id": med.id,
            "slot_time": "08:00",
            "status": "TAKEN",
        },
    )

    # 4. Medication deactivate
    await async_client.post(
        f"/medications/{med.id}/deactivate",
        data={"csrf_token": csrf_token},
    )

    # 5. Appointment schedule
    await async_client.post(
        "/appointments",
        data={
            "csrf_token": csrf_token,
            "doctor_name": "Dr. Audit",
            "specialty": "General",
            "location": "City Clinic",
            "appointment_datetime": "2026-11-20T10:00",
        },
    )

    entries = await memory_repo.list_audit_entries("default_profile")
    actions = {e.action for e in entries}

    assert "MEDICATION_CREATED" in actions
    assert "MEDICATION_UPDATED" in actions
    assert "MEDICATION_DEACTIVATED" in actions
    assert "DOSE_LOGGED" in actions
    assert "APPOINTMENT_CREATED" in actions

    for entry in entries:
        assert senior.passcode_hash not in str(entry.details)
        assert senior.passcode_salt not in str(entry.details)
        assert "pass123" not in str(entry.details)
