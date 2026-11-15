from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.clock import Clock
from app.config import Settings, get_settings
from app.dependencies import (
    SESSION_COOKIE_NAME,
    get_clock,
    get_repository,
    verify_csrf,
)
from app.repositories import BaseRepository
from app.services.auth import (
    create_session_cookie,
    verify_dummy_passcode,
    verify_passcode,
)
from app.services.rate_limiter import RateLimiter, extract_client_ip

router = APIRouter(tags=["Auth"])
templates = Jinja2Templates(directory="app/templates")

_login_rate_limiter: RateLimiter | None = None


def get_login_rate_limiter(clock: Annotated[Clock, Depends(get_clock)]) -> RateLimiter:
    global _login_rate_limiter
    if _login_rate_limiter is None or _login_rate_limiter.clock is not clock:
        _login_rate_limiter = RateLimiter(clock=clock, max_attempts=5, window_seconds=300)
    return _login_rate_limiter


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    setup: str | None = None,
) -> HTMLResponse:
    """Render accessible senior-friendly login form."""
    info_message = (
        "Care profile successfully created! Please log in." if setup == "success" else None
    )
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"request": request, "info_message": info_message},
    )


@router.post("/login", response_model=None)
async def process_login(
    request: Request,
    repo: Annotated[BaseRepository, Depends(get_repository)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
    limiter: Annotated[RateLimiter, Depends(get_login_rate_limiter)],
    name: Annotated[str, Form()],
    passcode: Annotated[str, Form()],
) -> Response:
    """Process member login with timing-safe verification and rate limiting."""
    client_ip = extract_client_ip(request)
    is_limited, retry_after = limiter.is_rate_limited(client_ip, name)
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Please retry after {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    # Generic error message to prevent account enumeration
    generic_error = "Name or passcode is incorrect"

    member = await repo.get_member_by_name("default_profile", name)
    if not member:
        # Dummy verification to prevent timing attack leaks
        verify_dummy_passcode(passcode)
        limiter.record_failure(client_ip, name)
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"request": request, "error": generic_error, "name": name},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Verify passcode
    is_valid_passcode = verify_passcode(passcode, member.passcode_salt, member.passcode_hash)
    if not is_valid_passcode or not member.is_active:
        limiter.record_failure(client_ip, name)
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"request": request, "error": generic_error, "name": name},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Successful login resets failure counters
    limiter.record_success(client_ip, name)

    # Create signed session cookie (8 hours expiry)
    session_val = create_session_cookie(
        member_id=member.id,
        session_secret=settings.SESSION_SECRET,
        clock=clock,
        max_age_hours=8,
    )

    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_val,
        max_age=8 * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
    )
    return response


@router.post("/logout", dependencies=[Depends(verify_csrf)])
async def process_logout() -> Response:
    """Clear session cookie and redirect to login."""
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key=SESSION_COOKIE_NAME, httponly=True, samesite="lax")
    return response
