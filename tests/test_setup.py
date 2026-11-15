import uuid

import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.repositories import MemoryRepository


@pytest.mark.asyncio
async def test_setup_disabled_when_code_empty(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "SETUP_CODE", "")

    # GET disabled
    response = await async_client.get("/setup")
    assert response.status_code == 404

    # POST disabled
    response = await async_client.post(
        "/setup",
        data={
            "setup_code": "any",
            "senior_name": "Ramesh",
            "passcode": "pass123",
            "timezone": "Asia/Kolkata",
        },
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_setup_wrong_code_rejected(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "SETUP_CODE", "master-secret-123")

    response = await async_client.post(
        "/setup",
        data={
            "setup_code": "wrong-code",
            "senior_name": "Ramesh Sharma",
            "passcode": "pass123",
            "timezone": "Asia/Kolkata",
        },
    )
    assert response.status_code == 400
    assert "Invalid setup code" in response.text


@pytest.mark.asyncio
async def test_setup_invalid_timezone_rejected(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "SETUP_CODE", "master-secret-123")

    response = await async_client.post(
        "/setup",
        data={
            "setup_code": "master-secret-123",
            "senior_name": "Ramesh Sharma",
            "passcode": "pass123",
            "timezone": "Invalid/Fake_Zone",
        },
    )
    assert response.status_code == 400
    assert "Invalid timezone" in response.text


@pytest.mark.asyncio
async def test_setup_success_and_subsequent_disabled(
    async_client: AsyncClient,
    memory_repo: MemoryRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "SETUP_CODE", "master-secret-123")

    # Initial setup
    response = await async_client.post(
        "/setup",
        data={
            "setup_code": "master-secret-123",
            "senior_name": "Ramesh Sharma",
            "passcode": "pass123",
            "email": "senior@example.com",
            "timezone": "Asia/Kolkata",
        },
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login?setup=success"

    # Profile exists in repository
    profile = await memory_repo.get_profile("default_profile")
    assert profile is not None
    assert profile.senior_name == "Ramesh Sharma"

    # Senior member created with can_edit=True and uuid4 hex ID
    senior = await memory_repo.get_member_by_name("default_profile", "Ramesh Sharma")
    assert senior is not None
    assert senior.role.value == "senior"
    assert senior.can_edit is True
    assert senior.email == "senior@example.com"
    assert len(senior.id) == 32
    assert uuid.UUID(hex=senior.id).version == 4

    # Audit entry written
    audit_entries = await memory_repo.list_audit_entries("default_profile")
    assert any(e.action == "PROFILE_BOOTSTRAP" for e in audit_entries)

    # Second setup attempt must return 404 (permanently disabled)
    second_get = await async_client.get("/setup")
    assert second_get.status_code == 404

    second_post = await async_client.post(
        "/setup",
        data={
            "setup_code": "master-secret-123",
            "senior_name": "Another Name",
            "passcode": "pass123",
            "timezone": "Asia/Kolkata",
        },
    )
    assert second_post.status_code == 404


@pytest.mark.asyncio
async def test_setup_rejects_colon_in_senior_name(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "SETUP_CODE", "master-secret-123")

    response = await async_client.post(
        "/setup",
        data={
            "setup_code": "master-secret-123",
            "senior_name": "Ramesh:Sharma",
            "passcode": "pass123",
            "timezone": "Asia/Kolkata",
        },
    )
    assert response.status_code == 400
    assert "Senior name cannot contain" in response.text
