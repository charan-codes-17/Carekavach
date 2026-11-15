from datetime import datetime
from typing import Any

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


class FirestoreRepository(BaseRepository):
    """Production Firestore repository with lazy client initialization."""

    def __init__(self, project_id: str = "", credentials_json: str = "") -> None:
        self._project_id = project_id
        self._credentials_json = credentials_json
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            # Lazy import so tests and local runs without GCP credentials don't fail at import
            import json

            from google.cloud import firestore

            if self._credentials_json and self._credentials_json.strip():
                try:
                    cred_info = json.loads(self._credentials_json)
                except Exception:
                    raise ValueError(
                        "Failed to parse FIREBASE_CREDENTIALS_JSON as valid JSON"
                    ) from None

                if not isinstance(cred_info, dict):
                    raise ValueError("FIREBASE_CREDENTIALS_JSON must be a JSON object")

                from google.oauth2 import service_account

                try:
                    credentials = service_account.Credentials.from_service_account_info(cred_info)
                except Exception:
                    raise ValueError(
                        "Failed to construct credentials from FIREBASE_CREDENTIALS_JSON"
                    ) from None

                project_id = cred_info.get("project_id") or self._project_id
                if project_id:
                    self._client = firestore.AsyncClient(
                        project=project_id, credentials=credentials
                    )
                else:
                    self._client = firestore.AsyncClient(credentials=credentials)
            else:
                if self._project_id:
                    self._client = firestore.AsyncClient(project=self._project_id)
                else:
                    self._client = firestore.AsyncClient()
        return self._client

    async def get_profile(self, profile_id: str) -> Profile | None:
        db = self._get_client()
        doc = await db.collection("profiles").document(profile_id).get()
        if not doc.exists:
            return None
        return Profile(**doc.to_dict())

    async def create_profile(self, profile: Profile) -> Profile:
        from google.cloud.exceptions import Conflict

        db = self._get_client()
        doc_ref = db.collection("profiles").document(profile.id)
        try:
            await doc_ref.create(profile.model_dump(mode="json"))
        except Conflict as exc:
            raise AlreadyExistsError(f"Profile {profile.id} already exists") from exc
        return profile

    async def get_member_by_id(self, profile_id: str, member_id: str) -> Member | None:
        db = self._get_client()
        doc = (
            await db.collection("profiles")
            .document(profile_id)
            .collection("members")
            .document(member_id)
            .get()
        )
        if not doc.exists:
            return None
        return Member(**doc.to_dict())

    async def get_member_by_name(self, profile_id: str, name: str) -> Member | None:
        db = self._get_client()
        members_ref = db.collection("profiles").document(profile_id).collection("members")
        target = name.strip().lower()
        # Stream members to perform case-insensitive name match
        async for doc in members_ref.stream():
            data = doc.to_dict()
            if data.get("name", "").strip().lower() == target:
                return Member(**data)
        return None

    async def create_member(self, member: Member) -> Member:
        from google.cloud.exceptions import Conflict

        existing = await self.get_member_by_name(member.profile_id, member.name)
        if existing:
            raise AlreadyExistsError(f"Member with name '{member.name}' already exists in profile")

        db = self._get_client()
        doc_ref = (
            db.collection("profiles")
            .document(member.profile_id)
            .collection("members")
            .document(member.id)
        )
        try:
            await doc_ref.create(member.model_dump(mode="json"))
        except Conflict as exc:
            raise AlreadyExistsError(f"Member ID {member.id} already exists") from exc
        return member

    async def update_member(self, member: Member) -> Member:
        db = self._get_client()
        doc_ref = (
            db.collection("profiles")
            .document(member.profile_id)
            .collection("members")
            .document(member.id)
        )
        await doc_ref.set(member.model_dump(mode="json"))
        return member

    async def list_members(self, profile_id: str) -> list[Member]:
        db = self._get_client()
        members_ref = db.collection("profiles").document(profile_id).collection("members")
        members: list[Member] = []
        async for doc in members_ref.stream():
            members.append(Member(**doc.to_dict()))
        return members

    async def get_medication(self, profile_id: str, medication_id: str) -> Medication | None:
        db = self._get_client()
        doc = (
            await db.collection("profiles")
            .document(profile_id)
            .collection("medications")
            .document(medication_id)
            .get()
        )
        if not doc.exists:
            return None
        return Medication(**doc.to_dict())

    async def create_medication(self, medication: Medication) -> Medication:
        from google.cloud.exceptions import Conflict

        db = self._get_client()
        doc_ref = (
            db.collection("profiles")
            .document(medication.profile_id)
            .collection("medications")
            .document(medication.id)
        )
        try:
            await doc_ref.create(medication.model_dump(mode="json"))
        except Conflict as exc:
            raise AlreadyExistsError(f"Medication {medication.id} already exists") from exc
        return medication

    async def update_medication(self, medication: Medication) -> Medication:
        db = self._get_client()
        doc_ref = (
            db.collection("profiles")
            .document(medication.profile_id)
            .collection("medications")
            .document(medication.id)
        )
        await doc_ref.set(medication.model_dump(mode="json"))
        return medication

    async def list_medications(self, profile_id: str, active_only: bool = True) -> list[Medication]:
        db = self._get_client()
        query = db.collection("profiles").document(profile_id).collection("medications")
        if active_only:
            query = query.where("is_active", "==", True)

        meds: list[Medication] = []
        async for doc in query.stream():
            meds.append(Medication(**doc.to_dict()))
        return sorted(meds, key=lambda m: m.name.lower())

    async def create_dose_log(self, dose_log: DoseLog) -> DoseLog:
        from google.cloud.exceptions import Conflict

        db = self._get_client()
        doc_ref = (
            db.collection("profiles")
            .document(dose_log.profile_id)
            .collection("dose_logs")
            .document(dose_log.id)
        )
        try:
            # create() fails if document exists
            await doc_ref.create(dose_log.model_dump(mode="json"))
        except Conflict as exc:
            raise AlreadyExistsError(f"Dose slot {dose_log.id} is already logged") from exc
        return dose_log

    async def get_dose_log(self, profile_id: str, log_id: str) -> DoseLog | None:
        db = self._get_client()
        doc = (
            await db.collection("profiles")
            .document(profile_id)
            .collection("dose_logs")
            .document(log_id)
            .get()
        )
        if not doc.exists:
            return None
        return DoseLog(**doc.to_dict())

    async def list_dose_logs(
        self, profile_id: str, start_date: str, end_date: str
    ) -> list[DoseLog]:
        db = self._get_client()
        query = (
            db.collection("profiles")
            .document(profile_id)
            .collection("dose_logs")
            .where("scheduled_date", ">=", start_date)
            .where("scheduled_date", "<=", end_date)
        )
        logs: list[DoseLog] = []
        async for doc in query.stream():
            logs.append(DoseLog(**doc.to_dict()))
        return sorted(logs, key=lambda log_item: (log_item.scheduled_date, log_item.scheduled_time))

    async def create_appointment(self, appointment: Appointment) -> Appointment:
        from google.cloud.exceptions import Conflict

        db = self._get_client()
        doc_ref = (
            db.collection("profiles")
            .document(appointment.profile_id)
            .collection("appointments")
            .document(appointment.id)
        )
        try:
            await doc_ref.create(appointment.model_dump(mode="json"))
        except Conflict as exc:
            raise AlreadyExistsError(f"Appointment {appointment.id} already exists") from exc
        return appointment

    async def get_appointment(self, profile_id: str, appointment_id: str) -> Appointment | None:
        db = self._get_client()
        doc = (
            await db.collection("profiles")
            .document(profile_id)
            .collection("appointments")
            .document(appointment_id)
            .get()
        )
        if not doc.exists:
            return None
        return Appointment(**doc.to_dict())

    async def list_appointments(
        self, profile_id: str, upcoming_only: bool = False, now: datetime | None = None
    ) -> list[Appointment]:
        db = self._get_client()
        query = db.collection("profiles").document(profile_id).collection("appointments")
        if upcoming_only and now is not None:
            query = query.where("appointment_datetime", ">=", now)
        appts: list[Appointment] = []
        async for doc in query.stream():
            appts.append(Appointment(**doc.to_dict()))
        return sorted(appts, key=lambda a: a.appointment_datetime)

    async def create_audit_entry(self, audit_entry: AuditEntry) -> AuditEntry:
        db = self._get_client()
        doc_ref = (
            db.collection("profiles")
            .document(audit_entry.profile_id)
            .collection("audit_entries")
            .document(audit_entry.id)
        )
        await doc_ref.set(audit_entry.model_dump(mode="json"))
        return audit_entry

    async def list_audit_entries(self, profile_id: str, limit: int = 50) -> list[AuditEntry]:
        db = self._get_client()
        query = (
            db.collection("profiles")
            .document(profile_id)
            .collection("audit_entries")
            .order_by("timestamp", direction="DESCENDING")
            .limit(limit)
        )
        entries: list[AuditEntry] = []
        async for doc in query.stream():
            entries.append(AuditEntry(**doc.to_dict()))
        return entries

    async def create_reminder_notification(
        self, notification: ReminderNotification
    ) -> ReminderNotification:
        from google.cloud.exceptions import Conflict

        db = self._get_client()
        doc_ref = (
            db.collection("profiles")
            .document(notification.profile_id)
            .collection("reminder_notifications")
            .document(notification.id)
        )
        try:
            await doc_ref.create(notification.model_dump(mode="json"))
        except Conflict as exc:
            msg = f"Reminder notification {notification.id} already dispatched"
            raise AlreadyExistsError(msg) from exc
        return notification

    async def get_reminder_notification(
        self, profile_id: str, notification_id: str
    ) -> ReminderNotification | None:
        db = self._get_client()
        doc = (
            await db.collection("profiles")
            .document(profile_id)
            .collection("reminder_notifications")
            .document(notification_id)
            .get()
        )
        if not doc.exists:
            return None
        return ReminderNotification(**doc.to_dict())

    async def ping_db(self) -> bool:
        db = self._get_client()
        test_ref = db.collection("_healthcheck").document("ping")
        await test_ref.set({"status": "ok"})
        doc = await test_ref.get()
        if not doc.exists:
            return False
        await test_ref.delete()
        return True
