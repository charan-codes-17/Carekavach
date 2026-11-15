from datetime import datetime

from app.models import (
    Appointment,
    AuditEntry,
    DoseLog,
    Medication,
    Member,
    Profile,
    ReminderNotification,
)
from app.repositories.base import AlreadyExistsError, BaseRepository


class MemoryRepository(BaseRepository):
    """Fast, in-memory reference implementation of BaseRepository for testing and local dev."""

    def __init__(self) -> None:
        self.profiles: dict[str, Profile] = {}
        self.members: dict[tuple[str, str], Member] = {}  # (profile_id, member_id) -> Member
        self.medications: dict[tuple[str, str], Medication] = {}  # (profile_id, med_id) -> Med
        self.dose_logs: dict[tuple[str, str], DoseLog] = {}  # (profile_id, log_id) -> DoseLog
        self.appointments: dict[tuple[str, str], Appointment] = {}  # (profile_id, appt_id) -> Appt
        self.audit_entries: dict[str, list[AuditEntry]] = {}  # profile_id -> list[AuditEntry]
        self.reminder_notifications: dict[tuple[str, str], ReminderNotification] = {}

    async def get_profile(self, profile_id: str) -> Profile | None:
        return self.profiles.get(profile_id)

    async def create_profile(self, profile: Profile) -> Profile:
        if profile.id in self.profiles:
            raise AlreadyExistsError(f"Profile {profile.id} already exists")
        self.profiles[profile.id] = profile
        return profile

    async def get_member_by_id(self, profile_id: str, member_id: str) -> Member | None:
        return self.members.get((profile_id, member_id))

    async def get_member_by_name(self, profile_id: str, name: str) -> Member | None:
        target_name = name.strip().lower()
        for member in self.members.values():
            if member.profile_id == profile_id and member.name.strip().lower() == target_name:
                return member
        return None

    async def create_member(self, member: Member) -> Member:
        existing = await self.get_member_by_name(member.profile_id, member.name)
        if existing:
            raise AlreadyExistsError(f"Member with name '{member.name}' already exists in profile")
        key = (member.profile_id, member.id)
        if key in self.members:
            raise AlreadyExistsError(f"Member ID {member.id} already exists")
        self.members[key] = member
        return member

    async def update_member(self, member: Member) -> Member:
        key = (member.profile_id, member.id)
        self.members[key] = member
        return member

    async def list_members(self, profile_id: str) -> list[Member]:
        return [m for m in self.members.values() if m.profile_id == profile_id]

    async def get_medication(self, profile_id: str, medication_id: str) -> Medication | None:
        return self.medications.get((profile_id, medication_id))

    async def create_medication(self, medication: Medication) -> Medication:
        key = (medication.profile_id, medication.id)
        if key in self.medications:
            raise AlreadyExistsError(f"Medication {medication.id} already exists")
        self.medications[key] = medication
        return medication

    async def update_medication(self, medication: Medication) -> Medication:
        key = (medication.profile_id, medication.id)
        self.medications[key] = medication
        return medication

    async def list_medications(self, profile_id: str, active_only: bool = True) -> list[Medication]:
        meds = [m for m in self.medications.values() if m.profile_id == profile_id]
        if active_only:
            meds = [m for m in meds if m.is_active]
        return sorted(meds, key=lambda m: m.name.lower())

    async def create_dose_log(self, dose_log: DoseLog) -> DoseLog:
        key = (dose_log.profile_id, dose_log.id)
        if key in self.dose_logs:
            raise AlreadyExistsError(f"Dose slot {dose_log.id} is already logged")
        self.dose_logs[key] = dose_log
        return dose_log

    async def get_dose_log(self, profile_id: str, log_id: str) -> DoseLog | None:
        return self.dose_logs.get((profile_id, log_id))

    async def list_dose_logs(
        self, profile_id: str, start_date: str, end_date: str
    ) -> list[DoseLog]:
        logs = [
            log
            for log in self.dose_logs.values()
            if log.profile_id == profile_id and start_date <= log.scheduled_date <= end_date
        ]
        return sorted(logs, key=lambda log_item: (log_item.scheduled_date, log_item.scheduled_time))

    async def create_appointment(self, appointment: Appointment) -> Appointment:
        key = (appointment.profile_id, appointment.id)
        if key in self.appointments:
            raise AlreadyExistsError(f"Appointment {appointment.id} already exists")
        self.appointments[key] = appointment
        return appointment

    async def get_appointment(self, profile_id: str, appointment_id: str) -> Appointment | None:
        return self.appointments.get((profile_id, appointment_id))

    async def list_appointments(
        self, profile_id: str, upcoming_only: bool = False, now: datetime | None = None
    ) -> list[Appointment]:
        appts = [a for a in self.appointments.values() if a.profile_id == profile_id]
        if upcoming_only and now is not None:
            appts = [a for a in appts if a.appointment_datetime >= now]
        return sorted(appts, key=lambda a: a.appointment_datetime)

    async def create_audit_entry(self, audit_entry: AuditEntry) -> AuditEntry:
        entries = self.audit_entries.setdefault(audit_entry.profile_id, [])
        entries.append(audit_entry)
        return audit_entry

    async def list_audit_entries(self, profile_id: str, limit: int = 50) -> list[AuditEntry]:
        entries = self.audit_entries.get(profile_id, [])
        return sorted(entries, key=lambda e: e.timestamp, reverse=True)[:limit]

    async def create_reminder_notification(
        self, notification: ReminderNotification
    ) -> ReminderNotification:
        key = (notification.profile_id, notification.id)
        if key in self.reminder_notifications:
            raise AlreadyExistsError(f"Reminder notification {notification.id} already dispatched")
        self.reminder_notifications[key] = notification
        return notification

    async def get_reminder_notification(
        self, profile_id: str, notification_id: str
    ) -> ReminderNotification | None:
        return self.reminder_notifications.get((profile_id, notification_id))

    async def ping_db(self) -> bool:
        test_key = "__ping_test__"
        self.profiles[test_key] = None  # type: ignore[assignment]
        del self.profiles[test_key]
        return True
