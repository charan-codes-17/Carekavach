import io
import sys
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

from app.clock import FixedClock
from app.config import Settings, get_settings
from app.main import app
from app.models import Appointment, DoseLog, DoseStatus, Medication, Member, MemberRole, Profile
from app.repositories import MemoryRepository

TZ = ZoneInfo("Asia/Kolkata")
SECRET = "test-scheduler-secret-key-at-least-32-chars"


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-Scheduler-Secret": SECRET}


async def setup_test_environment(
    repo: MemoryRepository,
    clock: FixedClock,
    base_time: datetime,
) -> tuple[Profile, Member, Member, Member]:
    """Helper to seed base profile and 3 members (Senior, Caretaker, Family)."""
    clock.set_time(base_time)

    profile = Profile(
        id="default_profile",
        senior_name="Ramesh Sharma",
        timezone="Asia/Kolkata",
        created_at=base_time - timedelta(days=30),
    )
    await repo.create_profile(profile)

    senior = Member(
        id="mem_senior",
        profile_id="default_profile",
        name="Ramesh Sharma",
        email="ramesh@example.com",
        role=MemberRole.SENIOR,
        can_edit=True,
        passcode_salt="salt",
        passcode_hash="hash",
        is_active=True,
        created_at=base_time - timedelta(days=30),
    )
    caretaker = Member(
        id="mem_care",
        profile_id="default_profile",
        name="Anil Kumar",
        email="anil@example.com",
        role=MemberRole.CARETAKER,
        can_edit=True,
        passcode_salt="salt",
        passcode_hash="hash",
        is_active=True,
        created_at=base_time - timedelta(days=30),
    )
    family = Member(
        id="mem_fam",
        profile_id="default_profile",
        name="Priya Sharma",
        email="priya@example.com",
        role=MemberRole.FAMILY,
        can_edit=False,
        passcode_salt="salt",
        passcode_hash="hash",
        is_active=True,
        created_at=base_time - timedelta(days=30),
    )

    await repo.create_member(senior)
    await repo.create_member(caretaker)
    await repo.create_member(family)

    return profile, senior, caretaker, family


@pytest.mark.asyncio
async def test_scheduler_endpoint_security_and_auth(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
) -> None:
    """Security verification for POST /tasks/run-reminders.

    - 404 when SCHEDULER_SECRET is unset
    - 401 when X-Scheduler-Secret header is missing
    - 401 when X-Scheduler-Secret header is invalid
    - 200 with JSON counts when secret matches
    """
    # 1. Unset SCHEDULER_SECRET -> 404
    app.dependency_overrides[get_settings] = lambda: Settings(
        SCHEDULER_SECRET="",
        EMAIL_BACKEND="log",
    )
    resp_unset = await async_client.post(
        "/tasks/run-reminders", headers={"X-Scheduler-Secret": "any"}
    )
    assert resp_unset.status_code == 404

    # 2. Configured secret
    app.dependency_overrides[get_settings] = lambda: Settings(
        SCHEDULER_SECRET=SECRET,
        EMAIL_BACKEND="log",
    )

    # Missing header -> 401
    resp_no_header = await async_client.post("/tasks/run-reminders")
    assert resp_no_header.status_code == 401
    assert "Missing" in resp_no_header.json()["detail"]

    # Wrong header -> 401
    resp_wrong_header = await async_client.post(
        "/tasks/run-reminders",
        headers={"X-Scheduler-Secret": "wrong-secret-value"},
    )
    assert resp_wrong_header.status_code == 401
    assert "Invalid" in resp_wrong_header.json()["detail"]

    # Valid secret -> 200 with pure JSON counts
    resp_valid = await async_client.post(
        "/tasks/run-reminders",
        headers={"X-Scheduler-Secret": SECRET},
    )
    assert resp_valid.status_code == 200
    data = resp_valid.json()
    assert set(data.keys()) == {"sent", "logged", "skipped_duplicate", "failed"}
    # Verify no personal data in response
    assert not any(key in str(data) for key in ["Ramesh", "Anil", "priya@example.com"])

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upcoming_dose_window_29_vs_31_minutes(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    auth_headers: dict[str, str],
) -> None:
    """Upcoming dose scan: 29 minutes ahead is triggered; 31 minutes ahead is not."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        SCHEDULER_SECRET=SECRET,
        EMAIL_BACKEND="log",
    )

    # Base time: 2026-11-15 08:00 AM Kolkata
    base_time = datetime(2026, 11, 15, 8, 0, tzinfo=TZ)
    await setup_test_environment(memory_repo, fixed_clock, base_time)

    # Medication created earlier this morning; scheduled at 08:30 AM
    med = Medication(
        id="med_upcoming",
        profile_id="default_profile",
        name="Aspirin",
        dosage="75mg",
        frequency="Daily",
        scheduled_times=["08:30"],
        instructions="With water",
        is_private=False,
        is_active=True,
        created_by="mem_senior",
        created_at=datetime(2026, 11, 15, 6, 0, tzinfo=TZ),
        updated_at=datetime(2026, 11, 15, 6, 0, tzinfo=TZ),
    )
    await memory_repo.create_medication(med)

    # Time 1: 07:59 AM (31 minutes before 08:30) -> Should NOT trigger
    fixed_clock.set_time(datetime(2026, 11, 15, 7, 59, tzinfo=TZ))
    resp1 = await async_client.post("/tasks/run-reminders", headers=auth_headers)
    assert resp1.status_code == 200
    counts1 = resp1.json()
    assert counts1["logged"] == 0
    assert counts1["sent"] == 0

    # Time 2: 08:01 AM (29 minutes before 08:30) -> MUST trigger!
    fixed_clock.set_time(datetime(2026, 11, 15, 8, 1, tzinfo=TZ))
    resp2 = await async_client.post("/tasks/run-reminders", headers=auth_headers)
    assert resp2.status_code == 200
    counts2 = resp2.json()
    # 3 active members (Senior, Caretaker, Family) receive reminder for non-private med
    assert counts2["logged"] == 3
    assert counts2["skipped_duplicate"] == 0

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_second_run_in_same_window_sends_nothing_new(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    auth_headers: dict[str, str],
) -> None:
    """Running twice in the same window sends once and skips duplicates on second run."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        SCHEDULER_SECRET=SECRET,
        EMAIL_BACKEND="log",
    )

    base_time = datetime(2026, 11, 15, 8, 10, tzinfo=TZ)
    await setup_test_environment(memory_repo, fixed_clock, base_time)

    # Medication scheduled at 08:30 (20 minutes away)
    med = Medication(
        id="med_idemp",
        profile_id="default_profile",
        name="Metformin",
        dosage="500mg",
        frequency="Daily",
        scheduled_times=["08:30"],
        instructions="After food",
        is_private=False,
        is_active=True,
        created_by="mem_senior",
        created_at=datetime(2026, 11, 15, 6, 0, tzinfo=TZ),
        updated_at=datetime(2026, 11, 15, 6, 0, tzinfo=TZ),
    )
    await memory_repo.create_medication(med)

    # First execution: Dispatches reminders
    resp_first = await async_client.post("/tasks/run-reminders", headers=auth_headers)
    assert resp_first.status_code == 200
    counts_first = resp_first.json()
    assert counts_first["logged"] == 3
    assert counts_first["skipped_duplicate"] == 0

    # Second execution in the same window: Nothing new dispatched, all skipped as duplicate
    resp_second = await async_client.post("/tasks/run-reminders", headers=auth_headers)
    assert resp_second.status_code == 200
    counts_second = resp_second.json()
    assert counts_second["logged"] == 0
    assert counts_second["sent"] == 0
    assert counts_second["skipped_duplicate"] == 3

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_private_medication_never_emailed_to_family(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    auth_headers: dict[str, str],
) -> None:
    """Private medication alerts go to Senior & Caretaker only; Family gets 0 emails."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        SCHEDULER_SECRET=SECRET,
        EMAIL_BACKEND="log",
    )

    base_time = datetime(2026, 11, 15, 8, 15, tzinfo=TZ)
    await setup_test_environment(memory_repo, fixed_clock, base_time)

    # Private medication scheduled at 08:30
    priv_med = Medication(
        id="med_priv_test",
        profile_id="default_profile",
        name="Private Medication X",
        dosage="20mg",
        frequency="Daily",
        scheduled_times=["08:30"],
        instructions="",
        is_private=True,
        is_active=True,
        created_by="mem_senior",
        created_at=datetime(2026, 11, 15, 6, 0, tzinfo=TZ),
        updated_at=datetime(2026, 11, 15, 6, 0, tzinfo=TZ),
    )
    await memory_repo.create_medication(priv_med)

    resp = await async_client.post("/tasks/run-reminders", headers=auth_headers)
    assert resp.status_code == 200
    counts = resp.json()
    # Exactly 2 dispatched: Senior and Caretaker. Family is excluded!
    assert counts["logged"] == 2

    # Verify notification records in repository: none should exist for mem_fam
    fam_key = "dose_upcoming_med_priv_test_2026-11-15_08:30_mem_fam"
    fam_notif = await memory_repo.get_reminder_notification("default_profile", fam_key)
    assert fam_notif is None

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_rule_a_overdue_via_tasks_endpoint(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    auth_headers: dict[str, str],
) -> None:
    """Rule A triggers at 60 min overdue; at 59 min it is pending."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        SCHEDULER_SECRET=SECRET,
        EMAIL_BACKEND="log",
    )

    base_time = datetime(2026, 11, 15, 8, 0, tzinfo=TZ)
    await setup_test_environment(memory_repo, fixed_clock, base_time)

    # Medication scheduled at 08:00 AM
    med = Medication(
        id="med_rule_a",
        profile_id="default_profile",
        name="Amlodipine",
        dosage="5mg",
        frequency="Daily",
        scheduled_times=["08:00"],
        instructions="",
        is_private=False,
        is_active=True,
        created_by="mem_senior",
        created_at=datetime(2026, 11, 15, 6, 0, tzinfo=TZ),
        updated_at=datetime(2026, 11, 15, 6, 0, tzinfo=TZ),
    )
    await memory_repo.create_medication(med)

    # At 08:59 (59 min past slot) -> Not yet 60 min overdue
    fixed_clock.set_time(datetime(2026, 11, 15, 8, 59, tzinfo=TZ))
    resp_59 = await async_client.post("/tasks/run-reminders", headers=auth_headers)
    assert resp_59.status_code == 200
    assert resp_59.json()["logged"] == 0

    # At 09:00 (60 min past slot) -> Rule A fires!
    fixed_clock.set_time(datetime(2026, 11, 15, 9, 0, tzinfo=TZ))
    resp_60 = await async_client.post("/tasks/run-reminders", headers=auth_headers)
    assert resp_60.status_code == 200
    # 3 active members receive Rule A escalation
    assert resp_60.json()["logged"] == 3

    # Running immediately again skips duplicates
    resp_second = await async_client.post("/tasks/run-reminders", headers=auth_headers)
    assert resp_second.json()["logged"] == 0
    assert resp_second.json()["skipped_duplicate"] == 3

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_rule_b_escalation_via_tasks_endpoint(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    auth_headers: dict[str, str],
) -> None:
    """Rule B triggers when 2 or more misses occur within the last 72 hours."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        SCHEDULER_SECRET=SECRET,
        EMAIL_BACKEND="log",
    )

    base_time = datetime(2026, 11, 16, 12, 0, tzinfo=TZ)
    await setup_test_environment(memory_repo, fixed_clock, base_time)

    # Medication created 2 days ago, scheduled daily at 08:00 AM
    med = Medication(
        id="med_rule_b",
        profile_id="default_profile",
        name="Metformin",
        dosage="500mg",
        frequency="Daily",
        scheduled_times=["08:00"],
        instructions="",
        is_private=False,
        is_active=True,
        created_by="mem_senior",
        created_at=datetime(2026, 11, 14, 6, 0, tzinfo=TZ),
        updated_at=datetime(2026, 11, 14, 6, 0, tzinfo=TZ),
    )
    await memory_repo.create_medication(med)

    # Dose on 2026-11-14 was TAKEN
    log_14 = DoseLog(
        id="med_rule_b_2026-11-14_08:00",
        profile_id="default_profile",
        medication_id="med_rule_b",
        medication_name="Metformin",
        scheduled_date="2026-11-14",
        scheduled_time="08:00",
        status=DoseStatus.TAKEN,
        logged_by_member_id="mem_senior",
        logged_by_name="Senior",
        logged_at=datetime(2026, 11, 14, 8, 5, tzinfo=TZ),
    )
    await memory_repo.create_dose_log(log_14)

    # Both 2026-11-15 08:00 and 2026-11-16 08:00 are missed (no logs).
    # Current time: 2026-11-16 12:00 PM (both slots are 60+ min overdue within last 72 hours).
    # This satisfies Rule B (2 misses in 72h) as well as Rule A for today.
    resp = await async_client.post("/tasks/run-reminders", headers=auth_headers)
    assert resp.status_code == 200
    counts = resp.json()

    # Rule A for today (3 members) + Rule B (3 members) = 6 logs dispatched
    assert counts["logged"] == 6

    # Verify Rule B notification record in repository
    rule_b_key = "escalation_rule_b_med_rule_b_2026-11-16_08:00_mem_care"
    notif = await memory_repo.get_reminder_notification("default_profile", rule_b_key)
    assert notif is not None
    assert notif.task_type == "escalation_rule_b"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_appointment_reminders_24h_2h_and_past(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    auth_headers: dict[str, str],
) -> None:
    """Appointment reminders fire at ~24h and ~2h (+/- 8 min), never for past appointments."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        SCHEDULER_SECRET=SECRET,
        EMAIL_BACKEND="log",
    )

    # Current time: 2026-11-15 10:00 AM Kolkata
    now_dt = datetime(2026, 11, 15, 10, 0, tzinfo=TZ)
    await setup_test_environment(memory_repo, fixed_clock, now_dt)

    # Appt 1: Exactly 24 hours away (2026-11-16 10:00 AM) -> Trigger 24h
    appt_24h = Appointment(
        id="appt_24h",
        profile_id="default_profile",
        doctor_name="Dr. Mehta",
        specialty="Cardiologist",
        location="Heart Care Clinic",
        appointment_datetime=now_dt + timedelta(hours=24),
        notes="Fast before checkup",
        created_by="mem_senior",
    )
    # Appt 2: Exactly 2 hours away (2026-11-15 12:00 PM) -> Trigger 2h
    appt_2h = Appointment(
        id="appt_2h",
        profile_id="default_profile",
        doctor_name="Dr. Rao",
        specialty="General",
        location="City Hospital",
        appointment_datetime=now_dt + timedelta(hours=2),
        notes="",
        created_by="mem_senior",
    )
    # Appt 3: 5 hours away -> Outside window
    appt_5h = Appointment(
        id="appt_5h",
        profile_id="default_profile",
        doctor_name="Dr. Sen",
        specialty="Dermatology",
        location="Skin Clinic",
        appointment_datetime=now_dt + timedelta(hours=5),
        notes="",
        created_by="mem_senior",
    )
    # Appt 4: In the past (1 hour ago) -> Should never trigger
    appt_past = Appointment(
        id="appt_past",
        profile_id="default_profile",
        doctor_name="Dr. Past",
        specialty="ENT",
        location="Clinic",
        appointment_datetime=now_dt - timedelta(hours=1),
        notes="",
        created_by="mem_senior",
    )

    await memory_repo.create_appointment(appt_24h)
    await memory_repo.create_appointment(appt_2h)
    await memory_repo.create_appointment(appt_5h)
    await memory_repo.create_appointment(appt_past)

    resp = await async_client.post("/tasks/run-reminders", headers=auth_headers)
    assert resp.status_code == 200
    counts = resp.json()
    # 2 appointments * 3 members = 6 dispatches
    assert counts["logged"] == 6

    # Verify notification records exist for 24h and 2h, but NOT for 5h or past
    key_24h = "appointment_reminder_24h_appt_24h_2026-11-16_10:00_mem_senior"
    key_2h = "appointment_reminder_2h_appt_2h_2026-11-15_12:00_mem_senior"
    key_5h = "appointment_reminder_2h_appt_5h_2026-11-15_15:00_mem_senior"

    assert await memory_repo.get_reminder_notification("default_profile", key_24h) is not None
    assert await memory_repo.get_reminder_notification("default_profile", key_2h) is not None
    assert await memory_repo.get_reminder_notification("default_profile", key_5h) is None

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_inactive_and_pre_created_slots_produce_no_reminders(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    auth_headers: dict[str, str],
) -> None:
    """Inactive medications and slots before creation time produce zero reminders."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        SCHEDULER_SECRET=SECRET,
        EMAIL_BACKEND="log",
    )

    # Current time: 08:15 AM
    now_dt = datetime(2026, 11, 15, 8, 15, tzinfo=TZ)
    await setup_test_environment(memory_repo, fixed_clock, now_dt)

    # Inactive med scheduled at 08:30 (15 min away)
    med_inactive = Medication(
        id="med_inact",
        profile_id="default_profile",
        name="Deactivated Med",
        dosage="10mg",
        frequency="Daily",
        scheduled_times=["08:30"],
        instructions="",
        is_private=False,
        is_active=False,
        created_by="mem_senior",
        created_at=now_dt - timedelta(days=1),
        updated_at=now_dt - timedelta(days=1),
    )
    # Med created at 08:45 AM (after the 08:30 slot today)
    med_future_created = Medication(
        id="med_fut",
        profile_id="default_profile",
        name="New Med",
        dosage="5mg",
        frequency="Daily",
        scheduled_times=["08:30"],
        instructions="",
        is_private=False,
        is_active=True,
        created_by="mem_senior",
        created_at=now_dt + timedelta(minutes=30),  # Created at 08:45 AM
        updated_at=now_dt + timedelta(minutes=30),
    )
    await memory_repo.create_medication(med_inactive)
    await memory_repo.create_medication(med_future_created)

    resp = await async_client.post("/tasks/run-reminders", headers=auth_headers)
    assert resp.status_code == 200
    counts = resp.json()
    assert counts["logged"] == 0
    assert counts["sent"] == 0

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_rule_b_one_vs_two_misses_inside_and_outside_72h_via_endpoint(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    auth_headers: dict[str, str],
) -> None:
    """Rule B via endpoint: 1 miss in 72h + 1 outside does not fire; 2 inside does."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        SCHEDULER_SECRET=SECRET,
        EMAIL_BACKEND="log",
    )

    # Base time: 2026-11-18 12:00 PM (cutoff 72h is 2026-11-15 12:00 PM)
    base_time = datetime(2026, 11, 18, 12, 0, tzinfo=TZ)
    await setup_test_environment(memory_repo, fixed_clock, base_time)

    med = Medication(
        id="med_rule_b_edge",
        profile_id="default_profile",
        name="Metformin",
        dosage="500mg",
        frequency="Daily",
        scheduled_times=["08:00"],
        instructions="",
        is_private=False,
        is_active=True,
        created_by="mem_senior",
        created_at=datetime(2026, 11, 14, 6, 0, tzinfo=TZ),
        updated_at=datetime(2026, 11, 14, 6, 0, tzinfo=TZ),
    )
    await memory_repo.create_medication(med)

    # Doses on Nov 14, Nov 16, and Nov 18 were taken
    for dt_str in ["2026-11-14", "2026-11-16", "2026-11-18"]:
        log = DoseLog(
            id=f"med_rule_b_edge_{dt_str}_08:00",
            profile_id="default_profile",
            medication_id="med_rule_b_edge",
            medication_name="Metformin",
            scheduled_date=dt_str,
            scheduled_time="08:00",
            status=DoseStatus.TAKEN,
            logged_by_member_id="mem_senior",
            logged_by_name="Senior",
            logged_at=datetime.fromisoformat(f"{dt_str}T08:05:00+05:30"),
        )
        await memory_repo.create_dose_log(log)

    # Misses: Nov 15 08:00 (76h ago, outside 72h) and Nov 17 08:00 (28h ago, inside 72h).
    # Since only 1 miss is inside 72h, Rule B must NOT fire!
    resp1 = await async_client.post("/tasks/run-reminders", headers=auth_headers)
    assert resp1.status_code == 200
    assert resp1.json()["logged"] == 0

    # Now simulate Nov 16 also missed by deleting its dose log
    del memory_repo.dose_logs[("default_profile", "med_rule_b_edge_2026-11-16_08:00")]

    # Now within 72h: Nov 16 (52h ago) and Nov 17 (28h ago) are both missed.
    # Exactly 2 misses inside 72h -> Rule B MUST trigger!
    resp2 = await async_client.post("/tasks/run-reminders", headers=auth_headers)
    assert resp2.status_code == 200
    assert resp2.json()["logged"] == 3

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_family_never_receives_private_med_in_mixed_escalation(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    auth_headers: dict[str, str],
) -> None:
    """In mixed overdue alerts, Family receives only public items; Senior and Caretaker get both."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        SCHEDULER_SECRET=SECRET,
        EMAIL_BACKEND="log",
    )

    base_time = datetime(2026, 11, 15, 9, 30, tzinfo=TZ)
    await setup_test_environment(memory_repo, fixed_clock, base_time)

    # Med 1: Private medication, overdue by 90 min
    med_priv = Medication(
        id="med_priv_alert",
        profile_id="default_profile",
        name="SensitiveMedicine",
        dosage="10mg",
        frequency="Daily",
        scheduled_times=["08:00"],
        instructions="",
        is_private=True,
        is_active=True,
        created_by="mem_senior",
        created_at=datetime(2026, 11, 15, 6, 0, tzinfo=TZ),
        updated_at=datetime(2026, 11, 15, 6, 0, tzinfo=TZ),
    )
    # Med 2: Public medication, overdue by 90 min
    med_pub = Medication(
        id="med_pub_alert",
        profile_id="default_profile",
        name="PublicVitamin",
        dosage="500mg",
        frequency="Daily",
        scheduled_times=["08:00"],
        instructions="",
        is_private=False,
        is_active=True,
        created_by="mem_senior",
        created_at=datetime(2026, 11, 15, 6, 0, tzinfo=TZ),
        updated_at=datetime(2026, 11, 15, 6, 0, tzinfo=TZ),
    )
    await memory_repo.create_medication(med_priv)
    await memory_repo.create_medication(med_pub)

    stdout_capture = io.StringIO()
    with patch.object(sys, "stdout", stdout_capture):
        resp = await async_client.post("/tasks/run-reminders", headers=auth_headers)

    assert resp.status_code == 200
    counts = resp.json()
    # 5 from Rule A (Senior priv+pub, Caretaker priv+pub, Family pub)
    # + 3 from Rule B (Senior, Caretaker, Family with pub only) = 8
    assert counts["logged"] == 8

    output = stdout_capture.getvalue()
    # Verify emails separated by recipient
    emails = output.split("EMAIL DISPATCH [LOG BACKEND]")

    family_emails = [e for e in emails if "priya@example.com" in e]
    assert len(family_emails) == 2
    for f_email in family_emails:
        # Every family email must contain PublicVitamin and strictly NOT contain SensitiveMedicine
        assert "PublicVitamin" in f_email
        assert "SensitiveMedicine" not in f_email

    caretaker_emails = [e for e in emails if "anil@example.com" in e]
    assert len(caretaker_emails) == 3
    caretaker_combined = "".join(caretaker_emails)
    assert "SensitiveMedicine" in caretaker_combined
    assert "PublicVitamin" in caretaker_combined

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_no_family_email_when_only_private_meds_overdue(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    auth_headers: dict[str, str],
) -> None:
    """When only private medications are overdue, family members receive zero emails."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        SCHEDULER_SECRET=SECRET,
        EMAIL_BACKEND="log",
    )

    base_time = datetime(2026, 11, 15, 9, 30, tzinfo=TZ)
    await setup_test_environment(memory_repo, fixed_clock, base_time)

    med_priv = Medication(
        id="med_priv_only",
        profile_id="default_profile",
        name="ClassifiedMed",
        dosage="5mg",
        frequency="Daily",
        scheduled_times=["08:00"],
        instructions="",
        is_private=True,
        is_active=True,
        created_by="mem_senior",
        created_at=datetime(2026, 11, 15, 6, 0, tzinfo=TZ),
        updated_at=datetime(2026, 11, 15, 6, 0, tzinfo=TZ),
    )
    await memory_repo.create_medication(med_priv)

    resp = await async_client.post("/tasks/run-reminders", headers=auth_headers)
    assert resp.status_code == 200
    counts = resp.json()
    # Only Senior and Caretaker are emailed (2)
    assert counts["logged"] == 2

    # Verify no notification created for Family member
    fam_key = "escalation_rule_a_med_priv_only_2026-11-15_08:00_mem_fam"
    assert await memory_repo.get_reminder_notification("default_profile", fam_key) is None

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_appointment_window_boundaries_and_past(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    auth_headers: dict[str, str],
) -> None:
    """Test precise appointment reminder boundaries (+/- 8 minutes for 24h and 2h)."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        SCHEDULER_SECRET=SECRET,
        EMAIL_BACKEND="log",
    )

    now_dt = datetime(2026, 11, 15, 10, 0, tzinfo=TZ)
    await setup_test_environment(memory_repo, fixed_clock, now_dt)

    # 1. 24h - 7 min (1433 min, within [1432, 1448]) -> TRIGGERS
    appt_24h_in = Appointment(
        id="appt_24h_in",
        profile_id="default_profile",
        doctor_name="Dr. Mehta",
        specialty="Cardiology",
        location="Heart Care",
        appointment_datetime=now_dt + timedelta(minutes=1433),
        notes="",
        created_by="mem_senior",
    )
    # 2. 24h + 10 min (1450 min, outside [1432, 1448]) -> SKIPPED
    appt_24h_out = Appointment(
        id="appt_24h_out",
        profile_id="default_profile",
        doctor_name="Dr. Out",
        specialty="General",
        location="Clinic",
        appointment_datetime=now_dt + timedelta(minutes=1450),
        notes="",
        created_by="mem_senior",
    )
    # 3. 2h + 7 min (127 min, within [112, 128]) -> TRIGGERS
    appt_2h_in = Appointment(
        id="appt_2h_in",
        profile_id="default_profile",
        doctor_name="Dr. Rao",
        specialty="Dental",
        location="Dental Care",
        appointment_datetime=now_dt + timedelta(minutes=127),
        notes="",
        created_by="mem_senior",
    )
    # 4. 2h - 15 min (105 min, outside [112, 128]) -> SKIPPED
    appt_2h_out = Appointment(
        id="appt_2h_out",
        profile_id="default_profile",
        doctor_name="Dr. Early",
        specialty="General",
        location="Clinic",
        appointment_datetime=now_dt + timedelta(minutes=105),
        notes="",
        created_by="mem_senior",
    )

    await memory_repo.create_appointment(appt_24h_in)
    await memory_repo.create_appointment(appt_24h_out)
    await memory_repo.create_appointment(appt_2h_in)
    await memory_repo.create_appointment(appt_2h_out)

    resp = await async_client.post("/tasks/run-reminders", headers=auth_headers)
    assert resp.status_code == 200
    counts = resp.json()
    # Exactly 2 appointments trigger * 3 members = 6 logs
    assert counts["logged"] == 6

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_failed_email_backend_falls_back_to_log_without_raising_in_tasks(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    auth_headers: dict[str, str],
) -> None:
    """When SMTP fails/times out, task endpoint catches it, falls back to log, and returns 200."""
    secret_pass = "CONFIDENTIAL_SMTP_SECRET_98765"
    app.dependency_overrides[get_settings] = lambda: Settings(
        SCHEDULER_SECRET=SECRET,
        EMAIL_BACKEND="smtp",
        SMTP_HOST="smtp.test.com",
        SMTP_PORT=587,
        SMTP_USER="smtp_user",
        SMTP_PASSWORD=secret_pass,
    )

    base_time = datetime(2026, 11, 15, 8, 1, tzinfo=TZ)
    await setup_test_environment(memory_repo, fixed_clock, base_time)

    # Upcoming medication at 08:30 (29 min away)
    med = Medication(
        id="med_smtp_fail",
        profile_id="default_profile",
        name="Aspirin",
        dosage="75mg",
        frequency="Daily",
        scheduled_times=["08:30"],
        instructions="",
        is_private=False,
        is_active=True,
        created_by="mem_senior",
        created_at=datetime(2026, 11, 15, 6, 0, tzinfo=TZ),
        updated_at=datetime(2026, 11, 15, 6, 0, tzinfo=TZ),
    )
    await memory_repo.create_medication(med)

    stdout_capture = io.StringIO()
    with (
        patch("smtplib.SMTP", side_effect=Exception(f"Connection timeout with {secret_pass}")),
        patch.object(sys, "stdout", stdout_capture),
    ):
        resp = await async_client.post("/tasks/run-reminders", headers=auth_headers)

    # Endpoint must NOT raise 500
    assert resp.status_code == 200
    counts = resp.json()
    # Fell back to log backend, so all 3 are recorded as 'logged'
    assert counts["logged"] == 3
    assert counts["failed"] == 0

    output = stdout_capture.getvalue()
    # Secret must NEVER appear in output
    assert secret_pass not in output
    # Rendered email must be present
    assert "Aspirin" in output

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_inactive_and_pre_created_overdue_slots_produce_no_escalation(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    auth_headers: dict[str, str],
) -> None:
    """Overdue slots for inactive meds or before created_at never trigger Rule A or Rule B."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        SCHEDULER_SECRET=SECRET,
        EMAIL_BACKEND="log",
    )

    now_dt = datetime(2026, 11, 15, 10, 0, tzinfo=TZ)
    await setup_test_environment(memory_repo, fixed_clock, now_dt)

    # 1. Inactive medication scheduled 2 hours ago (08:00 AM)
    med_inactive = Medication(
        id="med_inact_overdue",
        profile_id="default_profile",
        name="Archived Med",
        dosage="10mg",
        frequency="Daily",
        scheduled_times=["08:00"],
        instructions="",
        is_private=False,
        is_active=False,
        created_by="mem_senior",
        created_at=now_dt - timedelta(days=5),
        updated_at=now_dt - timedelta(days=1),
    )
    # 2. Active med created at 09:00 AM today with an 08:00 AM scheduled slot (pre-created slot)
    med_pre = Medication(
        id="med_pre_overdue",
        profile_id="default_profile",
        name="New Med",
        dosage="5mg",
        frequency="Daily",
        scheduled_times=["08:00"],
        instructions="",
        is_private=False,
        is_active=True,
        created_by="mem_senior",
        created_at=now_dt - timedelta(hours=1),  # 09:00 AM
        updated_at=now_dt - timedelta(hours=1),
    )
    await memory_repo.create_medication(med_inactive)
    await memory_repo.create_medication(med_pre)

    resp = await async_client.post("/tasks/run-reminders", headers=auth_headers)
    assert resp.status_code == 200
    counts = resp.json()
    assert counts["logged"] == 0
    assert counts["sent"] == 0

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_second_run_multi_event_sends_nothing_new(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    fixed_clock: FixedClock,
    auth_headers: dict[str, str],
) -> None:
    """Multi-event test: upcoming + overdue + appt dispatched once, skipped on second run."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        SCHEDULER_SECRET=SECRET,
        EMAIL_BACKEND="log",
    )

    now_dt = datetime(2026, 11, 15, 9, 0, tzinfo=TZ)
    await setup_test_environment(memory_repo, fixed_clock, now_dt)

    # 1. Overdue dose: scheduled at 08:00 AM (60 min overdue) -> Rule A
    med_overdue = Medication(
        id="med_multi_overdue",
        profile_id="default_profile",
        name="Blood Pressure Med",
        dosage="10mg",
        frequency="Daily",
        scheduled_times=["08:00"],
        instructions="",
        is_private=False,
        is_active=True,
        created_by="mem_senior",
        created_at=now_dt - timedelta(hours=3),
        updated_at=now_dt - timedelta(hours=3),
    )
    # 2. Upcoming dose: scheduled at 09:20 AM (20 min away) -> Upcoming
    med_upcoming = Medication(
        id="med_multi_upcoming",
        profile_id="default_profile",
        name="Eye Drops",
        dosage="1 drop",
        frequency="Daily",
        scheduled_times=["09:20"],
        instructions="",
        is_private=False,
        is_active=True,
        created_by="mem_senior",
        created_at=now_dt - timedelta(hours=3),
        updated_at=now_dt - timedelta(hours=3),
    )
    # 3. Appointment: in 2 hours (11:00 AM) -> 2h appointment reminder
    appt = Appointment(
        id="appt_multi",
        profile_id="default_profile",
        doctor_name="Dr. Gupta",
        specialty="Optometrist",
        location="Vision Eye Care",
        appointment_datetime=now_dt + timedelta(hours=2),
        notes="",
        created_by="mem_senior",
    )

    await memory_repo.create_medication(med_overdue)
    await memory_repo.create_medication(med_upcoming)
    await memory_repo.create_appointment(appt)

    # First run: All dispatched
    resp1 = await async_client.post("/tasks/run-reminders", headers=auth_headers)
    assert resp1.status_code == 200
    counts1 = resp1.json()
    # 3 events * 3 members = 9 dispatches
    assert counts1["logged"] == 9
    assert counts1["skipped_duplicate"] == 0

    # Second run in the same window: ZERO dispatched, all 9 skipped as duplicate!
    resp2 = await async_client.post("/tasks/run-reminders", headers=auth_headers)
    assert resp2.status_code == 200
    counts2 = resp2.json()
    assert counts2["logged"] == 0
    assert counts2["sent"] == 0
    assert counts2["skipped_duplicate"] == 9

    app.dependency_overrides.clear()
