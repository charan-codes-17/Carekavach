import secrets
from typing import Any

from app.clock import Clock
from app.models import AuditEntry
from app.repositories import BaseRepository


async def record_audit_event(
    repo: BaseRepository,
    clock: Clock,
    actor_name: str,
    action: str,
    details: dict[str, Any],
    profile_id: str = "default_profile",
) -> AuditEntry:
    """Record an immutable audit log entry."""
    entry = AuditEntry(
        id=secrets.token_hex(8),
        profile_id=profile_id,
        action=action,
        actor_name=actor_name,
        details=details,
        timestamp=clock.now_utc(),
    )
    return await repo.create_audit_entry(entry)
