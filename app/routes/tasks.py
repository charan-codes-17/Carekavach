import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.clock import Clock
from app.config import Settings, get_settings
from app.dependencies import get_clock, get_repository
from app.repositories import BaseRepository
from app.services.reminder_runner import run_reminders

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/run-reminders")
async def trigger_run_reminders(
    repo: Annotated[BaseRepository, Depends(get_repository)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
    x_scheduler_secret: Annotated[str | None, Header(alias="X-Scheduler-Secret")] = None,
) -> dict[str, int]:
    """Protected task endpoint triggered periodically by Cloud Scheduler cron.

    Verification rules:
    - If SCHEDULER_SECRET is unset or empty -> 404 Not Found.
    - If X-Scheduler-Secret header is missing or incorrect -> 401 Unauthorized.
    - Constant-time secret comparison on UTF-8 bytes.
    - No user session or CSRF token required.
    """
    if not settings.SCHEDULER_SECRET:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduler task endpoint is disabled",
        )

    if not x_scheduler_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing X-Scheduler-Secret header",
        )

    is_valid = secrets.compare_digest(
        x_scheduler_secret.encode("utf-8"),
        settings.SCHEDULER_SECRET.encode("utf-8"),
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid scheduler secret",
        )

    return await run_reminders(repo=repo, clock=clock, settings=settings)
