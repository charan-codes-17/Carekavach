from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

from app.clock import FixedClock
from app.config import get_settings
from app.dependencies import SESSION_COOKIE_NAME
from app.models import DoseStatus, Medication, Member, MemberRole, Profile
from app.repositories import MemoryRepository
from app.services.adherence import compute_slot_status, derived_misses
from app.services.auth import create_session_cookie, generate_csrf_token, hash_passcode


@pytest.fixture
def test_medication() -> Medication:
    """Fixture providing a test medication created at 06:00 IST."""
    tz = ZoneInfo("Asia/Kolkata")
    created_dt = datetime(2026, 11, 15, 6, 0, tzinfo=tz).astimezone(UTC)
    return Medication(
        id="med_test_1",
        profile_id="default_profile",
        name="Metformin",
        dosage="500mg",
        frequency="Twice daily",
        scheduled_times=["08:00", "20:00"],
        instructions="After meals",
        is_private=False,
        is_active=True,
        created_by="Senior",
        created_at=created_dt,
        updated_at=created_dt,
    )


def test_derived_status_boundary_59_60_61_minutes(test_medication: Medication) -> None:
    tz = ZoneInfo("Asia/Kolkata")
    date_str = "2026-11-15"
    time_str = "08:00"  # 8:00 AM IST

    # 1. Exactly 59 minutes past (08:59 IST) -> PENDING
    at_59 = datetime(2026, 11, 15, 8, 59, tzinfo=tz)
    status_59, label_59 = compute_slot_status(
        medication=test_medication,
        scheduled_date=date_str,
        scheduled_time=time_str,
        log=None,
        now=at_59,
        tz=tz,
    )
    assert status_59 == "PENDING"
    assert "Due at 8:00 AM" in label_59

    # 2. Exactly 60 minutes past (09:00 IST) -> MISSED
    at_60 = datetime(2026, 11, 15, 9, 0, tzinfo=tz)
    status_60, label_60 = compute_slot_status(
        medication=test_medication,
        scheduled_date=date_str,
        scheduled_time=time_str,
        log=None,
        now=at_60,
        tz=tz,
    )
    assert status_60 == "MISSED"
    assert "Missed - overdue" in label_60

    # 3. 61 minutes past (09:01 IST) -> MISSED
    at_61 = datetime(2026, 11, 15, 9, 1, tzinfo=tz)
    status_61, label_61 = compute_slot_status(
        medication=test_medication,
        scheduled_date=date_str,
        scheduled_time=time_str,
        log=None,
        now=at_61,
        tz=tz,
    )
    assert status_61 == "MISSED"


def test_slot_before_medication_creation_never_missed() -> None:
    tz = ZoneInfo("Asia/Kolkata")
    # Medication created at 10:00 AM IST
    created_dt = datetime(2026, 11, 15, 10, 0, tzinfo=tz).astimezone(UTC)
    med = Medication(
        id="med_new",
        profile_id="default_profile",
        name="Night Pill",
        dosage="10mg",
        frequency="Daily",
        scheduled_times=["08:00"],  # Slot is 08:00 AM, before creation at 10:00 AM
        instructions="",
        is_private=False,
        is_active=True,
        created_by="Senior",
        created_at=created_dt,
        updated_at=created_dt,
    )

    # Now is 11:30 AM IST (past 60 min after 08:00)
    now_dt = datetime(2026, 11, 15, 11, 30, tzinfo=tz)
    status_code, label = compute_slot_status(
        medication=med,
        scheduled_date="2026-11-15",
        scheduled_time="08:00",
        log=None,
        now=now_dt,
        tz=tz,
    )
    # Must NOT be MISSED because slot was before creation
    assert status_code == "PENDING"
    assert "Scheduled for 8:00 AM" in label


def test_timezone_conversion_utc_to_ist(test_medication: Medication) -> None:
    tz = ZoneInfo("Asia/Kolkata")
    # 08:00 AM IST corresponds to 02:30 AM UTC
    # 60 minutes overdue is 09:00 AM IST = 03:30 AM UTC
    utc_at_60 = datetime(2026, 11, 15, 3, 30, tzinfo=UTC)

    status_code, _ = compute_slot_status(
        medication=test_medication,
        scheduled_date="2026-11-15",
        scheduled_time="08:00",
        log=None,
        now=utc_at_60,
        tz=tz,
    )
    assert status_code == "MISSED"


def test_derived_misses_helper(test_medication: Medication) -> None:
    tz = ZoneInfo("Asia/Kolkata")
    now_dt = datetime(2026, 11, 17, 12, 0, tzinfo=tz)
    start_d = date(2026, 11, 15)
    end_d = date(2026, 11, 16)

    # No logs: 2 days * 2 scheduled slots = 4 misses
    misses = derived_misses([test_medication], [], start_d, end_d, now_dt, tz)
    assert len(misses) == 4
    assert misses[0]["slot_id"] == "med_test_1_2026-11-15_08:00"


@pytest.fixture
async def setup_dose_environment(
    memory_repo: MemoryRepository, fixed_clock: FixedClock
) -> tuple[Member, Medication]:
    """Create profile, senior, and an active medication."""
    profile = Profile(
        id="default_profile",
        senior_name="Grandpa Ramesh",
        timezone="Asia/Kolkata",
        created_at=fixed_clock.now_utc(),
    )
    await memory_repo.create_profile(profile)

    salt, p_hash = hash_passcode("secret123")
    senior = Member(
        id="senior_1",
        profile_id="default_profile",
        name="Ramesh Sharma",
        role=MemberRole.SENIOR,
        can_edit=True,
        passcode_salt=salt,
        passcode_hash=p_hash,
        is_active=True,
        created_at=fixed_clock.now_utc(),
    )
    await memory_repo.create_member(senior)

    med = Medication(
        id="med_1",
        profile_id="default_profile",
        name="Amlodipine",
        dosage="5mg",
        frequency="Daily",
        scheduled_times=["08:00", "20:00"],
        instructions="Morning",
        is_private=False,
        is_active=True,
        created_by="Ramesh",
        created_at=fixed_clock.now_utc(),
        updated_at=fixed_clock.now_utc(),
    )
    await memory_repo.create_medication(med)
    return senior, med


@pytest.mark.asyncio
async def test_dose_log_double_logging_returns_409(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    setup_dose_environment: tuple[Member, Medication],
) -> None:
    senior, med = setup_dose_environment
    settings = get_settings()

    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)
    csrf_token = generate_csrf_token(senior_cookie, settings.SESSION_SECRET)

    # 1. First dose log succeeds
    res1 = await async_client.post(
        "/doses/log",
        data={
            "csrf_token": csrf_token,
            "medication_id": med.id,
            "slot_time": "08:00",
            "status": "TAKEN",
        },
    )
    assert res1.status_code == 303

    tz = ZoneInfo("Asia/Kolkata")
    today_str = fixed_clock.now_utc().astimezone(tz).strftime("%Y-%m-%d")
    logs = await memory_repo.list_dose_logs("default_profile", today_str, today_str)
    assert len(logs) == 1
    assert logs[0].status == DoseStatus.TAKEN

    # 2. Duplicate log for exact same slot triggers 409 Conflict
    res2 = await async_client.post(
        "/doses/log",
        data={
            "csrf_token": csrf_token,
            "medication_id": med.id,
            "slot_time": "08:00",
            "status": "SKIPPED",
        },
    )
    assert res2.status_code == 409
    assert "Dose already logged by Ramesh Sharma" in res2.text

    # Still only one record exists in repo
    logs_after = await memory_repo.list_dose_logs("default_profile", today_str, today_str)
    assert len(logs_after) == 1


@pytest.mark.asyncio
async def test_dose_log_validation_errors(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    setup_dose_environment: tuple[Member, Medication],
) -> None:
    senior, med = setup_dose_environment
    settings = get_settings()

    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)
    csrf_token = generate_csrf_token(senior_cookie, settings.SESSION_SECRET)

    # 1. Wrong slot time not in scheduled_times
    res1 = await async_client.post(
        "/doses/log",
        data={
            "csrf_token": csrf_token,
            "medication_id": med.id,
            "slot_time": "14:00",  # Not in ["08:00", "20:00"]
            "status": "TAKEN",
        },
    )
    assert res1.status_code == 400
    assert "not part of medication schedule" in res1.text

    # 2. Inactive medication rejected
    med.is_active = False
    await memory_repo.update_medication(med)

    res2 = await async_client.post(
        "/doses/log",
        data={
            "csrf_token": csrf_token,
            "medication_id": med.id,
            "slot_time": "08:00",
            "status": "TAKEN",
        },
    )
    assert res2.status_code == 400
    assert "inactive" in res2.text


@pytest.mark.asyncio
async def test_dose_log_missing_csrf_rejected(
    async_client: AsyncClient,
    fixed_clock: FixedClock,
    setup_dose_environment: tuple[Member, Medication],
) -> None:
    senior, med = setup_dose_environment
    settings = get_settings()

    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)

    # Missing CSRF
    res = await async_client.post(
        "/doses/log",
        data={
            "medication_id": med.id,
            "slot_time": "08:00",
            "status": "TAKEN",
        },
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_dose_log_non_today_date_rejected(
    async_client: AsyncClient,
    fixed_clock: FixedClock,
    setup_dose_environment: tuple[Member, Medication],
) -> None:
    senior, med = setup_dose_environment
    settings = get_settings()

    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)
    csrf_token = generate_csrf_token(senior_cookie, settings.SESSION_SECRET)

    # 1. Yesterday rejected
    res_past = await async_client.post(
        "/doses/log",
        data={
            "csrf_token": csrf_token,
            "medication_id": med.id,
            "slot_date": "2026-11-14",
            "slot_time": "08:00",
            "status": "TAKEN",
        },
    )
    assert res_past.status_code == 400
    assert "only be logged for today" in res_past.text

    # 2. Tomorrow rejected
    res_future = await async_client.post(
        "/doses/log",
        data={
            "csrf_token": csrf_token,
            "medication_id": med.id,
            "slot_date": "2026-11-16",
            "slot_time": "08:00",
            "status": "TAKEN",
        },
    )
    assert res_future.status_code == 400
    assert "only be logged for today" in res_future.text

    # 3. Today succeeds
    res_today = await async_client.post(
        "/doses/log",
        data={
            "csrf_token": csrf_token,
            "medication_id": med.id,
            "slot_date": "2026-11-15",
            "slot_time": "08:00",
            "status": "TAKEN",
        },
    )
    assert res_today.status_code == 303


@pytest.mark.asyncio
async def test_private_medication_doses_hidden_from_family_on_doses_today(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
) -> None:
    settings = get_settings()
    now = fixed_clock.now_utc()

    # Create Senior and Family member
    profile = Profile(
        id="default_profile",
        senior_name="Grandpa Ramesh",
        timezone="Asia/Kolkata",
        created_at=now,
    )
    await memory_repo.create_profile(profile)

    salt1, hash1 = hash_passcode("pass123")
    senior = Member(
        id="senior_dose_priv",
        profile_id="default_profile",
        name="Ramesh",
        role=MemberRole.SENIOR,
        can_edit=True,
        passcode_salt=salt1,
        passcode_hash=hash1,
        created_at=now,
    )
    await memory_repo.create_member(senior)

    salt2, hash2 = hash_passcode("pass123")
    family = Member(
        id="family_dose_priv",
        profile_id="default_profile",
        name="Asha",
        role=MemberRole.FAMILY,
        can_edit=False,
        passcode_salt=salt2,
        passcode_hash=hash2,
        created_at=now,
    )
    await memory_repo.create_member(family)

    # 1 Public med + 1 Private med
    public_med = Medication(
        id="med_pub_1",
        profile_id="default_profile",
        name="Public Vitamin D",
        dosage="1000IU",
        frequency="Daily",
        scheduled_times=["08:00"],
        is_private=False,
        is_active=True,
        created_by="Ramesh",
        created_at=now,
        updated_at=now,
    )
    private_med = Medication(
        id="med_priv_1",
        profile_id="default_profile",
        name="Private Cardiac Drug",
        dosage="50mg",
        frequency="Daily",
        scheduled_times=["08:00"],
        is_private=True,
        is_active=True,
        created_by="Ramesh",
        created_at=now,
        updated_at=now,
    )
    await memory_repo.create_medication(public_med)
    await memory_repo.create_medication(private_med)

    # Senior view has both
    senior_cookie = create_session_cookie(senior.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, senior_cookie)
    res_sen = await async_client.get("/doses/today")
    assert res_sen.status_code == 200
    assert "Public Vitamin D" in res_sen.text
    assert "Private Cardiac Drug" in res_sen.text

    # Family view has ONLY public med
    family_cookie = create_session_cookie(family.id, settings.SESSION_SECRET, fixed_clock)
    async_client.cookies.set(SESSION_COOKIE_NAME, family_cookie)
    res_fam = await async_client.get("/doses/today")
    assert res_fam.status_code == 200
    assert "Public Vitamin D" in res_fam.text
    assert "Private Cardiac Drug" not in res_fam.text
