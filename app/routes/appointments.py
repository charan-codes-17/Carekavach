from datetime import UTC, datetime
import secrets
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
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
from app.models import Appointment, Member
from app.repositories import BaseRepository
from app.services.audit import record_audit_event
from app.services.auth import generate_csrf_token

router = APIRouter(prefix="/appointments", tags=["Appointments"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def list_appointments(
    request: Request,
    current_member: Annotated[Member, Depends(get_current_member)],
    repo: Annotated[BaseRepository, Depends(get_repository)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
    success: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    """List upcoming appointments sorted chronologically in profile timezone."""
    now = clock.now_utc()
    tz = ZoneInfo(settings.DEFAULT_TIMEZONE)

    # Filter upcoming only
    upcoming = await repo.list_appointments("default_profile", upcoming_only=True, now=now)

    session_cookie = request.cookies.get(SESSION_COOKIE_NAME, "")
    csrf_token = generate_csrf_token(session_cookie, settings.SESSION_SECRET)

    # Format appointment dates for display
    display_appts = []
    for a in upcoming:
        local_dt = a.appointment_datetime.astimezone(tz)
        display_appts.append(
            {
                "id": a.id,
                "doctor_name": a.doctor_name,
                "specialty": a.specialty,
                "location": a.location,
                "formatted_datetime": local_dt.strftime("%a, %d %b %Y at %I:%M %p").replace(" 0", " "),
                "notes": a.notes,
                "created_by": a.created_by,
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="appointments.html",
        context={
            "request": request,
            "current_member": current_member,
            "appointments": display_appts,
            "csrf_token": csrf_token,
            "success": success,
            "error": error,
        },
    )


@router.post("", response_model=None, dependencies=[Depends(verify_csrf)])
async def create_appointment(
    request: Request,
    current_member: Annotated[Member, Depends(require_editor)],
    repo: Annotated[BaseRepository, Depends(get_repository)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
    doctor_name: Annotated[str, Form()],
    specialty: Annotated[str, Form()],
    location: Annotated[str, Form()],
    appointment_datetime: Annotated[str, Form()],
    notes: Annotated[str, Form()] = "",
) -> Response:
    """Create upcoming doctor appointment."""
    tz = ZoneInfo(settings.DEFAULT_TIMEZONE)
    now = clock.now_utc()

    clean_doctor = doctor_name.strip()
    clean_specialty = specialty.strip()
    clean_location = location.strip()
    clean_notes = notes.strip() if notes else ""

    session_cookie = request.cookies.get(SESSION_COOKIE_NAME, "")
    csrf_token = generate_csrf_token(session_cookie, settings.SESSION_SECRET)

    if not clean_doctor or len(clean_doctor) > 80:
        return templates.TemplateResponse(
            request=request,
            name="appointments.html",
            context={
                "request": request,
                "current_member": current_member,
                "csrf_token": csrf_token,
                "error": "Doctor name is required (maximum 80 characters).",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not clean_specialty or len(clean_specialty) > 50:
        return templates.TemplateResponse(
            request=request,
            name="appointments.html",
            context={
                "request": request,
                "current_member": current_member,
                "csrf_token": csrf_token,
                "error": "Medical specialty is required (maximum 50 characters).",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not clean_location or len(clean_location) > 100:
        return templates.TemplateResponse(
            request=request,
            name="appointments.html",
            context={
                "request": request,
                "current_member": current_member,
                "csrf_token": csrf_token,
                "error": "Clinic / hospital location is required (maximum 100 characters).",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Parse datetime-local input
    try:
        dt_local = datetime.fromisoformat(appointment_datetime.strip())
        dt_tz = dt_local.replace(tzinfo=tz)
        dt_utc = dt_tz.astimezone(UTC)
    except Exception:
        return templates.TemplateResponse(
            request=request,
            name="appointments.html",
            context={
                "request": request,
                "current_member": current_member,
                "csrf_token": csrf_token,
                "error": "Invalid appointment date/time format.",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Past datetimes must be rejected
    if dt_utc <= now:
        return templates.TemplateResponse(
            request=request,
            name="appointments.html",
            context={
                "request": request,
                "current_member": current_member,
                "csrf_token": csrf_token,
                "error": "Appointment date and time must be in the future.",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    appt_id = secrets.token_hex(8)
    appt = Appointment(
        id=appt_id,
        profile_id="default_profile",
        doctor_name=clean_doctor,
        specialty=clean_specialty,
        location=clean_location,
        appointment_datetime=dt_utc,
        notes=clean_notes,
        created_by=current_member.name,
    )
    await repo.create_appointment(appt)

    await record_audit_event(
        repo=repo,
        clock=clock,
        actor_name=current_member.name,
        action="APPOINTMENT_CREATED",
        details={
            "doctor_name": clean_doctor,
            "specialty": clean_specialty,
            "appointment_datetime_utc": dt_utc.isoformat(),
        },
    )

    return RedirectResponse(
        url=f"/appointments?success=Appointment+with+'{clean_doctor}'+scheduled",
        status_code=status.HTTP_303_SEE_OTHER,
    )
