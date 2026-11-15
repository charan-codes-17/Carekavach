from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MemberRole(StrEnum):
    SENIOR = "senior"
    CARETAKER = "caretaker"
    FAMILY = "family"


class DoseStatus(StrEnum):
    TAKEN = "TAKEN"
    SKIPPED = "SKIPPED"


class Profile(BaseModel):
    id: str = "default_profile"
    senior_name: str
    timezone: str = "Asia/Kolkata"
    created_at: datetime


class Member(BaseModel):
    id: str
    profile_id: str = "default_profile"
    name: str
    email: str | None = None
    role: MemberRole
    can_edit: bool
    passcode_salt: str
    passcode_hash: str
    is_active: bool = True
    created_at: datetime


class Medication(BaseModel):
    id: str
    profile_id: str = "default_profile"
    name: str
    dosage: str
    frequency: str
    scheduled_times: list[str]  # e.g. ["08:00", "20:00"] wall-clock
    instructions: str = ""
    is_private: bool = False
    is_active: bool = True
    created_by: str
    created_at: datetime
    updated_at: datetime


class DoseLog(BaseModel):
    id: str  # {medication_id}_{date}_{time}
    profile_id: str = "default_profile"
    medication_id: str
    medication_name: str
    scheduled_date: str  # YYYY-MM-DD
    scheduled_time: str  # HH:MM
    status: DoseStatus
    logged_by_member_id: str
    logged_by_name: str
    logged_at: datetime


class Appointment(BaseModel):
    id: str
    profile_id: str = "default_profile"
    doctor_name: str
    specialty: str
    location: str
    appointment_datetime: datetime  # UTC stored
    notes: str = ""
    created_by: str


class AuditEntry(BaseModel):
    id: str
    profile_id: str = "default_profile"
    action: str
    actor_name: str
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime


class ReminderNotification(BaseModel):
    id: str  # {task_type}_{target_id}_{slot_date}_{slot_time}
    profile_id: str = "default_profile"
    task_type: str
    target_id: str
    sent_to: list[str] = Field(default_factory=list)
    sent_at: datetime
