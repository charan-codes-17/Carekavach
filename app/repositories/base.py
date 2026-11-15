from abc import ABC, abstractmethod
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


class AlreadyExistsError(Exception):
    """Raised when an entity with deterministic ID already exists."""


class BaseRepository(ABC):
    """Abstract interface defining all data storage contracts for CareKavach."""

    # --- Profile ---
    @abstractmethod
    async def get_profile(self, profile_id: str) -> Profile | None:
        """Retrieve care profile by ID."""

    @abstractmethod
    async def create_profile(self, profile: Profile) -> Profile:
        """Create a care profile."""

    # --- Member ---
    @abstractmethod
    async def get_member_by_id(self, profile_id: str, member_id: str) -> Member | None:
        """Retrieve a member by ID within a profile."""

    @abstractmethod
    async def get_member_by_name(self, profile_id: str, name: str) -> Member | None:
        """Retrieve a member by unique name within a profile."""

    @abstractmethod
    async def create_member(self, member: Member) -> Member:
        """Create a new member."""

    @abstractmethod
    async def update_member(self, member: Member) -> Member:
        """Update existing member data."""

    @abstractmethod
    async def list_members(self, profile_id: str) -> list[Member]:
        """List all members associated with the profile."""

    # --- Medication ---
    @abstractmethod
    async def get_medication(self, profile_id: str, medication_id: str) -> Medication | None:
        """Retrieve medication by ID."""

    @abstractmethod
    async def create_medication(self, medication: Medication) -> Medication:
        """Create a new medication record."""

    @abstractmethod
    async def update_medication(self, medication: Medication) -> Medication:
        """Update an existing medication."""

    @abstractmethod
    async def list_medications(self, profile_id: str, active_only: bool = True) -> list[Medication]:
        """List medications, optionally filtering to active ones."""

    # --- Dose Log ---
    @abstractmethod
    async def create_dose_log(self, dose_log: DoseLog) -> DoseLog:
        """Atomically create a dose log. Must raise AlreadyExistsError if slot already logged."""

    @abstractmethod
    async def get_dose_log(self, profile_id: str, log_id: str) -> DoseLog | None:
        """Retrieve dose log by deterministic slot ID."""

    @abstractmethod
    async def list_dose_logs(
        self, profile_id: str, start_date: str, end_date: str
    ) -> list[DoseLog]:
        """List dose logs in date range inclusive (YYYY-MM-DD)."""

    # --- Appointment ---
    @abstractmethod
    async def create_appointment(self, appointment: Appointment) -> Appointment:
        """Create a medical appointment."""

    @abstractmethod
    async def get_appointment(self, profile_id: str, appointment_id: str) -> Appointment | None:
        """Retrieve appointment by ID."""

    @abstractmethod
    async def list_appointments(
        self, profile_id: str, upcoming_only: bool = False, now: datetime | None = None
    ) -> list[Appointment]:
        """List appointments, optionally filtering to upcoming ones."""

    # --- Audit Entry ---
    @abstractmethod
    async def create_audit_entry(self, audit_entry: AuditEntry) -> AuditEntry:
        """Record an immutable audit log entry."""

    @abstractmethod
    async def list_audit_entries(self, profile_id: str, limit: int = 50) -> list[AuditEntry]:
        """List recent audit entries descending by timestamp."""

    # --- Reminder Notification ---
    @abstractmethod
    async def create_reminder_notification(
        self, notification: ReminderNotification
    ) -> ReminderNotification:
        """Atomically record notification dispatch. Must raise AlreadyExistsError if exists."""

    @abstractmethod
    async def get_reminder_notification(
        self, profile_id: str, notification_id: str
    ) -> ReminderNotification | None:
        """Retrieve reminder notification record by deterministic key."""

    # --- Diagnostics ---
    @abstractmethod
    async def ping_db(self) -> bool:
        """Check read/write readiness of repository."""
