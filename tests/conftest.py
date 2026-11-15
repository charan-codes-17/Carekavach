from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.clock import FixedClock
from app.config import Settings
from app.main import app
from app.repositories import MemoryRepository


@pytest.fixture
def memory_repo() -> MemoryRepository:
    """Provide a fresh in-memory repository for each test."""
    return MemoryRepository()


@pytest.fixture
def fixed_clock() -> FixedClock:
    """Provide a deterministic fixed clock."""
    return FixedClock()


@pytest.fixture
def test_settings() -> Settings:
    """Provide isolated test settings."""
    return Settings(
        USE_FIRESTORE=False,
        COOKIE_SECURE=False,
        SETUP_CODE="test-setup-code",
        SESSION_SECRET="test-session-secret-at-least-32-chars",
    )


@pytest.fixture
async def async_client(
    memory_repo: MemoryRepository, fixed_clock: FixedClock
) -> AsyncIterator[AsyncClient]:
    """Provide an async test client configured with in-memory state."""
    app.state.repository = memory_repo
    app.state.clock = fixed_clock

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
