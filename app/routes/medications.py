import re
import secrets
from typing import Annotated

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
from app.models import Medication, Member, MemberRole
from app.repositories import BaseRepository
from app.services.audit import record_audit_event
from app.services.auth import generate_csrf_token

router = APIRouter(prefix="/medications", tags=["Medications"])
templates = Jinja2Templates(directory="app/templates")

TIME_24H_REGEX = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def parse_and_validate_times(raw_times_str: str) -> tuple[list[str] | None, str | None]:
    """Parse comma/space/newline separated 24h HH:MM times, deduplicate, and sort.

    Returns (times_list, error_message).
    """
    if not raw_times_str or not raw_times_str.strip():
        return None, "At least one scheduled dose time (HH:MM) is required."

    tokens = [t.strip() for t in re.split(r"[\s,;]+", raw_times_str.strip()) if t.strip()]
    if not tokens:
        return None, "At least one scheduled dose time (HH:MM) is required."

    cleaned_set: set[str] = set()
    for token in tokens:
        # Normalize to HH:MM format (e.g. 8:00 -> 08:00)
        parts = token.split(":")
        if len(parts) == 2:
            h, m = parts[0].strip(), parts[1].strip()
            if len(h) == 1 and h.isdigit():
                token = f"0{h}:{m}"

        if not TIME_24H_REGEX.match(token):
            err_msg = (
                f"Invalid time format '{token}'. Use 24-hour HH:MM format (e.g. 08:00, 20:00)."
            )
            return None, err_msg
        cleaned_set.add(token)

    if len(cleaned_set) > 8:
        return None, "A medication may have at most 8 scheduled dose times per day."

    return sorted(cleaned_set), None


@router.get("", response_class=HTMLResponse)
async def list_medications(
    request: Request,
    current_member: Annotated[Member, Depends(get_current_member)],
    repo: Annotated[BaseRepository, Depends(get_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
    success: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    """List active medications.

    FAMILY role cannot view medications marked private.
    """
    all_meds = await repo.list_medications("default_profile", active_only=True)
    if current_member.role == MemberRole.FAMILY:
        meds = [m for m in all_meds if not m.is_private]
    else:
        meds = all_meds

    session_cookie = request.cookies.get(SESSION_COOKIE_NAME, "")
    csrf_token = generate_csrf_token(session_cookie, settings.SESSION_SECRET)

    return templates.TemplateResponse(
        request=request,
        name="medications_list.html",
        context={
            "request": request,
            "current_member": current_member,
            "medications": meds,
            "csrf_token": csrf_token,
            "success": success,
            "error": error,
        },
    )


@router.get("/new", response_class=HTMLResponse)
async def new_medication_form(
    request: Request,
    current_member: Annotated[Member, Depends(require_editor)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    """Render form to add a new medication schedule."""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME, "")
    csrf_token = generate_csrf_token(session_cookie, settings.SESSION_SECRET)

    return templates.TemplateResponse(
        request=request,
        name="medication_form.html",
        context={
            "request": request,
            "current_member": current_member,
            "csrf_token": csrf_token,
            "medication": None,
            "is_senior": current_member.role == MemberRole.SENIOR,
        },
    )


@router.post("", response_model=None, dependencies=[Depends(verify_csrf)])
async def create_medication(
    request: Request,
    current_member: Annotated[Member, Depends(require_editor)],
    repo: Annotated[BaseRepository, Depends(get_repository)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
    name: Annotated[str, Form()],
    dosage: Annotated[str, Form()],
    frequency: Annotated[str, Form()],
    scheduled_times: Annotated[str, Form()],
    instructions: Annotated[str, Form()] = "",
    is_private: Annotated[str | None, Form()] = None,
) -> Response:
    """Create a new medication record."""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME, "")
    csrf_token = generate_csrf_token(session_cookie, settings.SESSION_SECRET)

    clean_name = name.strip()
    clean_dosage = dosage.strip()
    clean_frequency = frequency.strip()
    clean_instructions = instructions.strip() if instructions else ""

    form_data = {
        "name": clean_name,
        "dosage": clean_dosage,
        "frequency": clean_frequency,
        "scheduled_times": scheduled_times,
        "instructions": clean_instructions,
    }

    if not clean_name or len(clean_name) > 80:
        return templates.TemplateResponse(
            request=request,
            name="medication_form.html",
            context={
                "request": request,
                "current_member": current_member,
                "csrf_token": csrf_token,
                "form_data": form_data,
                "error": "Medication name is required (maximum 80 characters).",
                "is_senior": current_member.role == MemberRole.SENIOR,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not clean_dosage or len(clean_dosage) > 50:
        return templates.TemplateResponse(
            request=request,
            name="medication_form.html",
            context={
                "request": request,
                "current_member": current_member,
                "csrf_token": csrf_token,
                "form_data": form_data,
                "error": "Dosage is required (maximum 50 characters).",
                "is_senior": current_member.role == MemberRole.SENIOR,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    times_list, time_err = parse_and_validate_times(scheduled_times)
    if time_err or not times_list:
        return templates.TemplateResponse(
            request=request,
            name="medication_form.html",
            context={
                "request": request,
                "current_member": current_member,
                "csrf_token": csrf_token,
                "form_data": form_data,
                "error": time_err or "Invalid times.",
                "is_senior": current_member.role == MemberRole.SENIOR,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Only SENIOR can set is_private; caretakers default to False
    private_flag = False
    if current_member.role == MemberRole.SENIOR and is_private is not None:
        private_flag = is_private.lower() in ("true", "1", "yes", "on")

    now = clock.now_utc()
    med_id = secrets.token_hex(8)
    med = Medication(
        id=med_id,
        profile_id="default_profile",
        name=clean_name,
        dosage=clean_dosage,
        frequency=clean_frequency or "Daily",
        scheduled_times=times_list,
        instructions=clean_instructions,
        is_private=private_flag,
        is_active=True,
        created_by=current_member.name,
        created_at=now,
        updated_at=now,
    )
    await repo.create_medication(med)

    await record_audit_event(
        repo=repo,
        clock=clock,
        actor_name=current_member.name,
        action="MEDICATION_CREATED",
        details={
            "medication_name": clean_name,
            "dosage": clean_dosage,
            "scheduled_times": times_list,
            "is_private": private_flag,
        },
    )

    return RedirectResponse(
        url=f"/medications?success=Medication+'{clean_name}'+added+successfully",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/{med_id}/edit", response_class=HTMLResponse)
async def edit_medication_form(
    med_id: str,
    request: Request,
    current_member: Annotated[Member, Depends(get_current_member)],
    repo: Annotated[BaseRepository, Depends(get_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    """Render edit form for medication."""
    med = await repo.get_medication("default_profile", med_id)
    if not med:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")

    # Privacy check: FAMILY returns 404
    if current_member.role == MemberRole.FAMILY and med.is_private:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")

    # Permission check: Editor required
    if not (current_member.role == MemberRole.SENIOR or current_member.can_edit):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Editor access required")

    session_cookie = request.cookies.get(SESSION_COOKIE_NAME, "")
    csrf_token = generate_csrf_token(session_cookie, settings.SESSION_SECRET)

    return templates.TemplateResponse(
        request=request,
        name="medication_form.html",
        context={
            "request": request,
            "current_member": current_member,
            "csrf_token": csrf_token,
            "medication": med,
            "times_str": ", ".join(med.scheduled_times),
            "is_senior": current_member.role == MemberRole.SENIOR,
        },
    )


@router.post("/{med_id}/edit", response_model=None, dependencies=[Depends(verify_csrf)])
async def update_medication(
    med_id: str,
    request: Request,
    current_member: Annotated[Member, Depends(get_current_member)],
    repo: Annotated[BaseRepository, Depends(get_repository)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
    name: Annotated[str, Form()],
    dosage: Annotated[str, Form()],
    frequency: Annotated[str, Form()],
    scheduled_times: Annotated[str, Form()],
    instructions: Annotated[str, Form()] = "",
    is_private: Annotated[str | None, Form()] = None,
) -> Response:
    """Update medication schedule."""
    med = await repo.get_medication("default_profile", med_id)
    if not med:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")

    # If FAMILY tries to access private med -> 404
    if current_member.role == MemberRole.FAMILY and med.is_private:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")

    # Permission check: Editor required
    if not (current_member.role == MemberRole.SENIOR or current_member.can_edit):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Editor access required")

    session_cookie = request.cookies.get(SESSION_COOKIE_NAME, "")
    csrf_token = generate_csrf_token(session_cookie, settings.SESSION_SECRET)

    clean_name = name.strip()
    clean_dosage = dosage.strip()
    clean_frequency = frequency.strip()
    clean_instructions = instructions.strip() if instructions else ""

    form_data = {
        "name": clean_name,
        "dosage": clean_dosage,
        "frequency": clean_frequency,
        "scheduled_times": scheduled_times,
        "instructions": clean_instructions,
    }

    if not clean_name or len(clean_name) > 80:
        return templates.TemplateResponse(
            request=request,
            name="medication_form.html",
            context={
                "request": request,
                "current_member": current_member,
                "csrf_token": csrf_token,
                "medication": med,
                "form_data": form_data,
                "error": "Medication name is required (maximum 80 characters).",
                "is_senior": current_member.role == MemberRole.SENIOR,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not clean_dosage or len(clean_dosage) > 50:
        return templates.TemplateResponse(
            request=request,
            name="medication_form.html",
            context={
                "request": request,
                "current_member": current_member,
                "csrf_token": csrf_token,
                "medication": med,
                "form_data": form_data,
                "error": "Dosage is required (maximum 50 characters).",
                "is_senior": current_member.role == MemberRole.SENIOR,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    times_list, time_err = parse_and_validate_times(scheduled_times)
    if time_err or not times_list:
        return templates.TemplateResponse(
            request=request,
            name="medication_form.html",
            context={
                "request": request,
                "current_member": current_member,
                "csrf_token": csrf_token,
                "medication": med,
                "form_data": form_data,
                "error": time_err or "Invalid times.",
                "is_senior": current_member.role == MemberRole.SENIOR,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Privacy preservation: Only SENIOR can change privacy; Caretakers keep existing value
    if current_member.role == MemberRole.SENIOR:
        privacy_val = is_private is not None and is_private.lower() in ("true", "1", "yes", "on")
    else:
        privacy_val = med.is_private

    med.name = clean_name
    med.dosage = clean_dosage
    med.frequency = clean_frequency or "Daily"
    med.scheduled_times = times_list
    med.instructions = clean_instructions
    med.is_private = privacy_val
    med.updated_at = clock.now_utc()

    await repo.update_medication(med)

    await record_audit_event(
        repo=repo,
        clock=clock,
        actor_name=current_member.name,
        action="MEDICATION_UPDATED",
        details={
            "medication_id": med_id,
            "medication_name": clean_name,
            "scheduled_times": times_list,
            "is_private": privacy_val,
        },
    )

    return RedirectResponse(
        url=f"/medications?success=Medication+'{clean_name}'+updated+successfully",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{med_id}/deactivate", dependencies=[Depends(verify_csrf)])
async def deactivate_medication(
    med_id: str,
    current_member: Annotated[Member, Depends(require_editor)],
    repo: Annotated[BaseRepository, Depends(get_repository)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> RedirectResponse:
    """Soft-deactivate medication schedule. Never hard-delete."""
    med = await repo.get_medication("default_profile", med_id)
    if not med:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")

    if current_member.role == MemberRole.FAMILY and med.is_private:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")

    med.is_active = False
    med.updated_at = clock.now_utc()
    await repo.update_medication(med)

    await record_audit_event(
        repo=repo,
        clock=clock,
        actor_name=current_member.name,
        action="MEDICATION_DEACTIVATED",
        details={"medication_id": med_id, "medication_name": med.name},
    )

    return RedirectResponse(
        url=f"/medications?success=Medication+'{med.name}'+deactivated",
        status_code=status.HTTP_303_SEE_OTHER,
    )
