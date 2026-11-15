from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.models import Appointment
from app.repositories.firestore import FirestoreRepository


class _FakeDocumentSnapshot:
    """Minimal Firestore document snapshot exposing ``to_dict``."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    @property
    def exists(self) -> bool:
        return True

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)


class _FakeQuery:
    """Chainable fake collection/document reference.

    Only ``stream`` is exercised by ``list_appointments``. ``where`` is guarded
    so the test fails loudly if the repository reintroduces a range query.
    """

    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = docs

    def collection(self, _name: str) -> "_FakeQuery":
        return self

    def document(self, _doc_id: str) -> "_FakeQuery":
        return self

    def where(self, *_args: Any, **_kwargs: Any) -> "_FakeQuery":
        raise AssertionError("list_appointments must not use a Firestore range query")

    async def stream(self) -> Any:
        for data in self._docs:
            yield _FakeDocumentSnapshot(data)


class _FakeFirestoreClient:
    """Fake AsyncClient rooted at a single collection of appointments."""

    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = docs

    def collection(self, _name: str) -> _FakeQuery:
        return _FakeQuery(self._docs)


def _stored_appointment_doc(
    *,
    appt_id: str,
    doctor_name: str,
    appointment_datetime: datetime,
) -> dict[str, Any]:
    """Serialise an appointment exactly as real Firestore receives it.

    ``create_appointment`` writes ``model_dump(mode="json")``, so the datetime is
    persisted as an ISO-8601 string rather than a native timestamp.
    """
    appointment = Appointment(
        id=appt_id,
        profile_id="default_profile",
        doctor_name=doctor_name,
        specialty="General",
        location="Clinic",
        appointment_datetime=appointment_datetime,
        created_by="Ramesh Sharma",
    )
    stored = appointment.model_dump(mode="json")
    assert isinstance(stored["appointment_datetime"], str)
    return stored


def _repository_with_docs(docs: list[dict[str, Any]]) -> FirestoreRepository:
    repo = FirestoreRepository()
    repo._client = _FakeFirestoreClient(docs)  # inject fake client, skip GCP auth
    return repo


@pytest.mark.asyncio
async def test_list_appointments_filters_future_and_sorts_ascending() -> None:
    now = datetime(2026, 11, 15, 8, 0, tzinfo=UTC)
    docs = [
        _stored_appointment_doc(
            appt_id="appt_later",
            doctor_name="Dr. Later",
            appointment_datetime=now + timedelta(days=5),
        ),
        _stored_appointment_doc(
            appt_id="appt_past",
            doctor_name="Dr. Past",
            appointment_datetime=now - timedelta(days=2),
        ),
        _stored_appointment_doc(
            appt_id="appt_sooner",
            doctor_name="Dr. Sooner",
            appointment_datetime=now + timedelta(days=2),
        ),
    ]
    repo = _repository_with_docs(docs)

    upcoming = await repo.list_appointments("default_profile", upcoming_only=True, now=now)

    # Past hidden, future shown, sorted ascending
    assert [a.id for a in upcoming] == ["appt_sooner", "appt_later"]
    assert all(a.appointment_datetime.tzinfo is not None for a in upcoming)


@pytest.mark.asyncio
async def test_list_appointments_returns_all_when_not_upcoming_only() -> None:
    now = datetime(2026, 11, 15, 8, 0, tzinfo=UTC)
    docs = [
        _stored_appointment_doc(
            appt_id="appt_past",
            doctor_name="Dr. Past",
            appointment_datetime=now - timedelta(days=1),
        ),
        _stored_appointment_doc(
            appt_id="appt_future",
            doctor_name="Dr. Future",
            appointment_datetime=now + timedelta(days=1),
        ),
    ]
    repo = _repository_with_docs(docs)

    all_appts = await repo.list_appointments("default_profile")

    assert [a.id for a in all_appts] == ["appt_past", "appt_future"]
