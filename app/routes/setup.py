import secrets
import uuid
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.clock import Clock
from app.config import Settings, get_settings
from app.dependencies import get_clock, get_repository
from app.models import Member, MemberRole, Profile
from app.repositories import BaseRepository
from app.services.audit import record_audit_event
from app.services.auth import hash_passcode
from app.services.rate_limiter import RateLimiter, extract_client_ip

router = APIRouter(prefix="/setup", tags=["Setup"])
templates = Jinja2Templates(directory="app/templates")

# Rate limiter for bootstrap route: max 5 attempts per 5 minutes per IP
_setup_rate_limiter: RateLimiter | None = None


def get_setup_rate_limiter(clock: Annotated[Clock, Depends(get_clock)]) -> RateLimiter:
    global _setup_rate_limiter
    if _setup_rate_limiter is None or _setup_rate_limiter.clock is not clock:
        _setup_rate_limiter = RateLimiter(clock=clock, max_attempts=5, window_seconds=300)
    return _setup_rate_limiter


@router.get("", response_class=HTMLResponse)
async def setup_page(
    request: Request,
    repo: Annotated[BaseRepository, Depends(get_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    """Render setup bootstrap page if not disabled."""
    if not settings.SETUP_CODE or not settings.SETUP_CODE.strip():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setup disabled")

    # Check if profile already exists
    existing = await repo.get_profile("default_profile")
    if existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setup permanently disabled: profile already exists",
        )

    return templates.TemplateResponse(
        request=request,
        name="setup.html",
        context={"request": request, "default_timezone": settings.DEFAULT_TIMEZONE},
    )


@router.post("", response_model=None)
async def process_setup(
    request: Request,
    repo: Annotated[BaseRepository, Depends(get_repository)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
    limiter: Annotated[RateLimiter, Depends(get_setup_rate_limiter)],
    setup_code: Annotated[str, Form()],
    senior_name: Annotated[str, Form()],
    passcode: Annotated[str, Form()],
    email: Annotated[str | None, Form()] = None,
    timezone_str: Annotated[str, Form(alias="timezone")] = "Asia/Kolkata",
) -> Response:
    """Process bootstrap profile creation."""
    if not settings.SETUP_CODE or not settings.SETUP_CODE.strip():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setup disabled")

    existing = await repo.get_profile("default_profile")
    if existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setup permanently disabled: profile already exists",
        )

    client_ip = extract_client_ip(request)
    is_limited, retry_after = limiter.is_rate_limited(client_ip, "setup")
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many setup attempts. Please retry after {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    # Constant-time comparison of setup code
    if not secrets.compare_digest(
        setup_code.strip().encode("utf-8"), settings.SETUP_CODE.strip().encode("utf-8")
    ):
        limiter.record_failure(client_ip, "setup")
        return templates.TemplateResponse(
            request=request,
            name="setup.html",
            context={
                "request": request,
                "error": "Invalid setup code. Verification failed.",
                "senior_name": senior_name,
                "email": email,
                "default_timezone": timezone_str,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Validate inputs
    senior_name = senior_name.strip()
    if not senior_name or len(senior_name) > 60:
        return templates.TemplateResponse(
            request=request,
            name="setup.html",
            context={
                "request": request,
                "error": "Senior name must be between 1 and 60 characters.",
                "senior_name": senior_name,
                "email": email,
                "default_timezone": timezone_str,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if ":" in senior_name:
        return templates.TemplateResponse(
            request=request,
            name="setup.html",
            context={
                "request": request,
                "error": "Senior name cannot contain ':'.",
                "senior_name": senior_name,
                "email": email,
                "default_timezone": timezone_str,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if len(passcode) < 6 or len(passcode) > 100:
        return templates.TemplateResponse(
            request=request,
            name="setup.html",
            context={
                "request": request,
                "error": "Passcode must be at least 6 characters long.",
                "senior_name": senior_name,
                "email": email,
                "default_timezone": timezone_str,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Validate timezone
    try:
        ZoneInfo(timezone_str.strip())
        clean_tz = timezone_str.strip()
    except (ZoneInfoNotFoundError, ValueError):
        return templates.TemplateResponse(
            request=request,
            name="setup.html",
            context={
                "request": request,
                "error": f"Invalid timezone '{timezone_str}'. Must be a valid IANA timezone.",
                "senior_name": senior_name,
                "email": email,
                "default_timezone": timezone_str,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Validate optional email format if provided
    clean_email = email.strip() if email and email.strip() else None
    if clean_email and ("@" not in clean_email or "." not in clean_email):
        return templates.TemplateResponse(
            request=request,
            name="setup.html",
            context={
                "request": request,
                "error": "Invalid email address format.",
                "senior_name": senior_name,
                "email": email,
                "default_timezone": timezone_str,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Create profile
    now = clock.now_utc()
    profile = Profile(
        id="default_profile",
        senior_name=senior_name,
        timezone=clean_tz,
        created_at=now,
    )
    await repo.create_profile(profile)

    # Create Senior member
    salt, p_hash = hash_passcode(passcode)
    member_id = uuid.uuid4().hex
    senior_member = Member(
        id=member_id,
        profile_id="default_profile",
        name=senior_name,
        email=clean_email,
        role=MemberRole.SENIOR,
        can_edit=True,
        passcode_salt=salt,
        passcode_hash=p_hash,
        is_active=True,
        created_at=now,
    )
    await repo.create_member(senior_member)

    # Record initial audit entry
    await record_audit_event(
        repo=repo,
        clock=clock,
        actor_name=senior_name,
        action="PROFILE_BOOTSTRAP",
        details={
            "senior_name": senior_name,
            "timezone": clean_tz,
            "has_email": clean_email is not None,
        },
    )

    limiter.record_success(client_ip, "setup")
    return RedirectResponse(url="/login?setup=success", status_code=status.HTTP_303_SEE_OTHER)
