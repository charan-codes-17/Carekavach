import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.clock import Clock
from app.config import Settings, get_settings
from app.dependencies import (
    SESSION_COOKIE_NAME,
    get_clock,
    get_current_member,
    get_repository,
    require_role,
    verify_csrf,
)
from app.models import Member, MemberRole
from app.repositories import AlreadyExistsError, BaseRepository
from app.services.audit import record_audit_event
from app.services.auth import generate_csrf_token, hash_passcode

router = APIRouter(prefix="/members", tags=["Members"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def list_members_page(
    request: Request,
    current_member: Annotated[Member, Depends(get_current_member)],
    repo: Annotated[BaseRepository, Depends(get_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
    error: str | None = None,
    success: str | None = None,
) -> HTMLResponse:
    """List members in profile.

    Emails are shown ONLY to the SENIOR.
    """
    members = await repo.list_members("default_profile")
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME, "")
    csrf_token = generate_csrf_token(session_cookie, settings.SESSION_SECRET)

    return templates.TemplateResponse(
        request=request,
        name="members.html",
        context={
            "request": request,
            "current_member": current_member,
            "members": members,
            "is_senior": current_member.role == MemberRole.SENIOR,
            "csrf_token": csrf_token,
            "error": error,
            "success": success,
        },
    )


@router.post(
    "/invite",
    dependencies=[Depends(verify_csrf), Depends(require_role(MemberRole.SENIOR))],
)
async def invite_member(
    request: Request,
    current_member: Annotated[Member, Depends(get_current_member)],
    repo: Annotated[BaseRepository, Depends(get_repository)],
    clock: Annotated[Clock, Depends(get_clock)],
    name: Annotated[str, Form()],
    role_str: Annotated[str, Form(alias="role")],
    passcode: Annotated[str, Form()],
    email: Annotated[str | None, Form()] = None,
    can_edit: Annotated[str | None, Form()] = None,
) -> RedirectResponse:
    """Senior invites a new Caretaker or Family member."""
    clean_name = name.strip()
    if not clean_name or len(clean_name) > 60:
        return RedirectResponse(
            url="/members?error=Member+name+must+be+between+1+and+60+characters",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if ":" in clean_name:
        return RedirectResponse(
            url="/members?error=Member+name+cannot+contain+colon",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    clean_role = role_str.strip().lower()
    if clean_role not in (MemberRole.CARETAKER.value, MemberRole.FAMILY.value):
        return RedirectResponse(
            url="/members?error=Invalid+role+selected",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    target_role = MemberRole(clean_role)

    if len(passcode) < 6 or len(passcode) > 100:
        return RedirectResponse(
            url="/members?error=Passcode+must+be+at+least+6+characters",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    clean_email = email.strip() if email and email.strip() else None
    if clean_email and ("@" not in clean_email or "." not in clean_email):
        return RedirectResponse(
            url="/members?error=Invalid+email+format",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # can_edit defaults: True for Caretaker, False for Family
    if can_edit is not None:
        has_edit_permission = can_edit.lower() in ("true", "1", "yes", "on")
    else:
        has_edit_permission = target_role == MemberRole.CARETAKER

    salt, p_hash = hash_passcode(passcode)
    new_member = Member(
        id=uuid.uuid4().hex,
        profile_id="default_profile",
        name=clean_name,
        email=clean_email,
        role=target_role,
        can_edit=has_edit_permission,
        passcode_salt=salt,
        passcode_hash=p_hash,
        is_active=True,
        created_at=clock.now_utc(),
    )

    try:
        await repo.create_member(new_member)
    except AlreadyExistsError:
        return RedirectResponse(
            url=f"/members?error=A+member+named+'{clean_name}'+already+exists",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    await record_audit_event(
        repo=repo,
        clock=clock,
        actor_name=current_member.name,
        action="MEMBER_INVITED",
        details={
            "invited_member_name": clean_name,
            "role": target_role.value,
            "can_edit": has_edit_permission,
            "has_email": clean_email is not None,
        },
    )

    return RedirectResponse(
        url=f"/members?success=Member+'{clean_name}'+invited+successfully",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/{member_id}/revoke",
    dependencies=[Depends(verify_csrf), Depends(require_role(MemberRole.SENIOR))],
)
async def revoke_member(
    member_id: str,
    current_member: Annotated[Member, Depends(get_current_member)],
    repo: Annotated[BaseRepository, Depends(get_repository)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> RedirectResponse:
    """Senior revokes a member's access. A senior cannot revoke themself."""
    if member_id == current_member.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senior cannot revoke their own access",
        )

    target_member = await repo.get_member_by_id("default_profile", member_id)
    if not target_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    target_member.is_active = False
    await repo.update_member(target_member)

    await record_audit_event(
        repo=repo,
        clock=clock,
        actor_name=current_member.name,
        action="MEMBER_REVOKED",
        details={"revoked_member_name": target_member.name, "member_id": member_id},
    )

    return RedirectResponse(
        url=f"/members?success=Access+for+'{target_member.name}'+revoked",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/{member_id}/can-edit",
    dependencies=[Depends(verify_csrf), Depends(require_role(MemberRole.SENIOR))],
)
async def toggle_can_edit(
    member_id: str,
    current_member: Annotated[Member, Depends(get_current_member)],
    repo: Annotated[BaseRepository, Depends(get_repository)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> RedirectResponse:
    """Senior toggles can_edit permission for a member."""
    target_member = await repo.get_member_by_id("default_profile", member_id)
    if not target_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    target_member.can_edit = not target_member.can_edit
    await repo.update_member(target_member)

    await record_audit_event(
        repo=repo,
        clock=clock,
        actor_name=current_member.name,
        action="MEMBER_CAN_EDIT_UPDATED",
        details={"member_name": target_member.name, "new_can_edit": target_member.can_edit},
    )

    status_word = "granted" if target_member.can_edit else "removed"
    return RedirectResponse(
        url=f"/members?success=Edit+permissions+{status_word}+for+'{target_member.name}'",
        status_code=status.HTTP_303_SEE_OTHER,
    )
