from datetime import UTC, datetime

import pytest

from app.models import (
    Appointment,
    AuditEntry,
    DoseLog,
    DoseStatus,
    Medication,
    Member,
    MemberRole,
    Profile,
    ReminderNotification,
)
from app.repositories import AlreadyExistsError, MemoryRepository


@pytest.mark.asyncio
async def test_profile_crud(memory_repo: MemoryRepository) -> None:
    profile = Profile(
        id="profile_1",
        senior_name="Grandpa Ramesh",
        timezone="Asia/Kolkata",
        created_at=datetime.now(UTC),
    )
    created = await memory_repo.create_profile(profile)
    assert created.id == "profile_1"

    fetched = await memory_repo.get_profile("profile_1")
    assert fetched is not None
    assert fetched.senior_name == "Grandpa Ramesh"

    # Duplicate creation raises AlreadyExistsError
    with pytest.raises(AlreadyExistsError):
        await memory_repo.create_profile(profile)


@pytest.mark.asyncio
async def test_member_crud_and_lookup_by_name(memory_repo: MemoryRepository) -> None:
    member = Member(
        id="mem_1",
        profile_id="profile_1",
        name="Ramesh Sharma",
        role=MemberRole.SENIOR,
        can_edit=True,
        passcode_salt="salt123",
        passcode_hash="hash123",
        created_at=datetime.now(UTC),
    )
    await memory_repo.create_member(member)

    # Lookup by name (case-insensitive)
    found = await memory_repo.get_member_by_name("profile_1", "ramesh sharma")
    assert found is not None
    assert found.id == "mem_1"

    # Duplicate name raises AlreadyExistsError
    duplicate_name_member = Member(
        id="mem_2",
        profile_id="profile_1",
        name="RAMESH SHARMA",
        role=MemberRole.CARETAKER,
        can_edit=True,
        passcode_salt="salt456",
        passcode_hash="hash456",
        created_at=datetime.now(UTC),
    )
    with pytest.raises(AlreadyExistsError):
        await memory_repo.create_member(duplicate_name_member)


@pytest.mark.asyncio
async def test_medication_crud_and_soft_deactivation(memory_repo: MemoryRepository) -> None:
    med = Medication(
        id="med_1",
        profile_id="profile_1",
        name="Metformin",
        dosage="500mg",
        frequency="Twice daily",
        scheduled_times=["08:00", "20:00"],
        instructions="After meals",
        is_private=False,
        is_active=True,
        created_by="mem_1",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await memory_repo.create_medication(med)

    active_meds = await memory_repo.list_medications("profile_1", active_only=True)
    assert len(active_meds) == 1

    # Soft-deactivate
    med.is_active = False
    await memory_repo.update_medication(med)

    active_after = await memory_repo.list_medications("profile_1", active_only=True)
    assert len(active_after) == 0

    all_meds = await memory_repo.list_medications("profile_1", active_only=False)
    assert len(all_meds) == 1


@pytest.mark.asyncio
async def test_atomic_dose_logging_prevents_duplicates(memory_repo: MemoryRepository) -> None:
    slot_id = "med_1_2026-11-15_08:00"
    dose_log = DoseLog(
        id=slot_id,
        profile_id="profile_1",
        medication_id="med_1",
        medication_name="Metformin",
        scheduled_date="2026-11-15",
        scheduled_time="08:00",
        status=DoseStatus.TAKEN,
        logged_by_member_id="mem_1",
        logged_by_name="Ramesh",
        logged_at=datetime.now(UTC),
    )
    created = await memory_repo.create_dose_log(dose_log)
    assert created.id == slot_id

    # Attempting to log the exact same slot again must raise AlreadyExistsError
    duplicate_log = DoseLog(
        id=slot_id,
        profile_id="profile_1",
        medication_id="med_1",
        medication_name="Metformin",
        scheduled_date="2026-11-15",
        scheduled_time="08:00",
        status=DoseStatus.SKIPPED,
        logged_by_member_id="mem_2",
        logged_by_name="Pooja (Caretaker)",
        logged_at=datetime.now(UTC),
    )
    with pytest.raises(AlreadyExistsError):
        await memory_repo.create_dose_log(duplicate_log)


@pytest.mark.asyncio
async def test_appointments_and_audit(memory_repo: MemoryRepository) -> None:
    appt1 = Appointment(
        id="appt_1",
        profile_id="profile_1",
        doctor_name="Dr. Mehta",
        specialty="Cardiologist",
        location="Apollo Clinic",
        appointment_datetime=datetime(2026, 11, 20, 10, 0, tzinfo=UTC),
        created_by="mem_1",
    )
    appt2 = Appointment(
        id="appt_2",
        profile_id="profile_1",
        doctor_name="Dr. Rao",
        specialty="Ophthalmologist",
        location="Eye Care Center",
        appointment_datetime=datetime(2026, 11, 18, 9, 0, tzinfo=UTC),
        created_by="mem_1",
    )
    await memory_repo.create_appointment(appt1)
    await memory_repo.create_appointment(appt2)

    appts = await memory_repo.list_appointments("profile_1")
    assert len(appts) == 2
    # Verify chronological sorting (appt2 earlier than appt1)
    assert appts[0].id == "appt_2"
    assert appts[1].id == "appt_1"

    # Audit entry recording
    entry = AuditEntry(
        id="audit_1",
        profile_id="profile_1",
        action="MEDICATION_ADDED",
        actor_name="Ramesh Sharma",
        details={"medication_name": "Metformin"},
        timestamp=datetime.now(UTC),
    )
    await memory_repo.create_audit_entry(entry)
    entries = await memory_repo.list_audit_entries("profile_1")
    assert len(entries) == 1
    assert entries[0].action == "MEDICATION_ADDED"


@pytest.mark.asyncio
async def test_reminder_notification_atomic_idempotency(memory_repo: MemoryRepository) -> None:
    notification_key = "upcoming_dose_med1_2026-11-15_08:00"
    notification = ReminderNotification(
        id=notification_key,
        profile_id="profile_1",
        task_type="upcoming_dose",
        target_id="med1",
        sent_to=["caretaker@example.com"],
        sent_at=datetime.now(UTC),
    )
    await memory_repo.create_reminder_notification(notification)

    # Duplicate notification key must be rejected to guarantee idempotency
    with pytest.raises(AlreadyExistsError):
        await memory_repo.create_reminder_notification(notification)


@pytest.mark.asyncio
async def test_ping_db(memory_repo: MemoryRepository) -> None:
    assert await memory_repo.ping_db() is True
