from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.clock import Clock
from app.config import Settings, get_settings
from app.dependencies import (
    SESSION_COOKIE_NAME,
    get_clock,
    get_current_member,
    get_repository,
    require_editor,
    verify_csrf,
)
from app.models import DoseLog, DoseStatus, Member, MemberRole
from app.repositories import AlreadyExistsError, BaseRepository
from app.services.adherence import get_today_slots
from app.services.audit import record_audit_event
from app.services.auth import generate_csrf_token

router = APIRouter(prefix="/doses", tags=["Doses"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/today", response_class=HTMLResponse)
async def today_doses_view(
    request: Request,
    current_member: Annotated[Member, Depends(get_current_member)],
    repo: Annotated[BaseRepository, Depends(get_repository)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
    success: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    """Timeline of today's scheduled dose slots with accessible text status labels."""
    tz = ZoneInfo(settings.DEFAULT_TIMEZONE)
    now = clock.now_utc()
    today_date_str = now.astimezone(tz).strftime("%Y-%m-%d")

    all_meds = await repo.list_medications("default_profile", active_only=True)
    if current_member.role == MemberRole.FAMILY:
        meds = [m for m in all_meds if not m.is_private]
    else:
        meds = all_meds

    logs = await repo.list_dose_logs("default_profile", today_date_str, today_date_str)
    slots = get_today_slots(meds, logs, now, tz)

    session_cookie = request.cookies.get(SESSION_COOKIE_NAME, "")
    csrf_token = generate_csrf_token(session_cookie, settings.SESSION_SECRET)

    return templates.TemplateResponse(
        request=request,
        name="doses_today.html",
        context={
            "request": request,
            "current_member": current_member,
            "slots": slots,
            "today_date": today_date_str,
            "csrf_token": csrf_token,
            "success": success,
            "error": error,
        },
    )


@router.post("/log", response_model=None, dependencies=[Depends(verify_csrf)])
async def log_dose(
    request: Request,
    current_member: Annotated[Member, Depends(require_editor)],
    repo: Annotated[BaseRepository, Depends(get_repository)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
    medication_id: Annotated[str, Form()],
    slot_time: Annotated[str, Form()],
    status_str: Annotated[str, Form(alias="status")],
    slot_date: Annotated[str | None, Form()] = None,
) -> Response:
    """Log a scheduled dose slot as TAKEN or SKIPPED. Prevents double-logging atomically."""
    tz = ZoneInfo(settings.DEFAULT_TIMEZONE)
    now = clock.now_utc()
    today_date_str = now.astimezone(tz).strftime("%Y-%m-%d")

    # Reject non-today date if explicitly provided
    if slot_date and slot_date.strip() != today_date_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Doses can only be logged for today ({today_date_str})",
        )

    med = await repo.get_medication("default_profile", medication_id)
    if not med or not med.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Medication not found or inactive",
        )

    # Privacy check for family members
    if current_member.role == MemberRole.FAMILY and med.is_private:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")

    if slot_time not in med.scheduled_times:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Slot '{slot_time}' is not part of medication schedule",
        )

    status_upper = status_str.strip().upper()
    if status_upper not in (DoseStatus.TAKEN.value, DoseStatus.SKIPPED.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status must be TAKEN or SKIPPED",
        )

    dose_status = DoseStatus(status_upper)
    slot_id = f"{med.id}_{today_date_str}_{slot_time}"

    dose_log = DoseLog(
        id=slot_id,
        profile_id="default_profile",
        medication_id=med.id,
        medication_name=med.name,
        scheduled_date=today_date_str,
        scheduled_time=slot_time,
        status=dose_status,
        logged_by_member_id=current_member.id,
        logged_by_name=current_member.name,
        logged_at=now,
    )

    try:
        await repo.create_dose_log(dose_log)
    except AlreadyExistsError:
        existing = await repo.get_dose_log("default_profile", slot_id)
        if existing:
            logged_time_str = existing.logged_at.astimezone(tz).strftime("%I:%M %p").lstrip("0")
            msg = f"Dose already logged by {existing.logged_by_name} at {logged_time_str}"
        else:
            msg = "Dose slot has already been logged"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)

    await record_audit_event(
        repo=repo,
        clock=clock,
        actor_name=current_member.name,
        action="DOSE_LOGGED",
        details={
            "medication_id": med.id,
            "medication_name": med.name,
            "slot_id": slot_id,
            "status": dose_status.value,
        },
    )

    return RedirectResponse(
        url=f"/doses/today?success=Dose+for+'{med.name}'+marked+as+{dose_status.value.lower()}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
