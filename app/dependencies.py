from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.clock import Clock
from app.config import Settings, get_settings
from app.models import Member, MemberRole
from app.repositories import BaseRepository
from app.services.auth import decode_session_cookie, verify_csrf_token

SESSION_COOKIE_NAME = "carekavach_session"


def get_repository(request: Request) -> BaseRepository:
    """Dependency provider for storage repository."""
    return request.app.state.repository  # type: ignore[no-any-return]


def get_clock(request: Request) -> Clock:
    """Dependency provider for system clock."""
    return request.app.state.clock  # type: ignore[no-any-return]


async def get_current_member(
    request: Request,
    repo: Annotated[BaseRepository, Depends(get_repository)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Member:
    """Retrieve and validate member from session cookie.

    RE-READS the member from the database on every request to verify is_active and role.
    Never trusts roles or status from the cookie.
    """
    cookie_value = request.cookies.get(SESSION_COOKIE_NAME)
    member_id = decode_session_cookie(cookie_value, settings.SESSION_SECRET, clock)

    if not member_id:
        accept = request.headers.get("accept", "")
        if "application/json" in accept and "text/html" not in accept:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )

    # Re-read member from repository
    member = await repo.get_member_by_id("default_profile", member_id)
    if not member or not member.is_active:
        accept = request.headers.get("accept", "")
        if "application/json" in accept and "text/html" not in accept:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account inactive or not found",
            )
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )

    return member


def require_role(*roles: MemberRole) -> Callable[[Member], Member]:
    """Dependency factory restricting access to specified roles."""

    def role_checker(member: Annotated[Member, Depends(get_current_member)]) -> Member:
        if member.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: insufficient role permissions",
            )
        return member

    return role_checker


async def require_editor(
    member: Annotated[Member, Depends(get_current_member)],
) -> Member:
    """Ensure member has editing privileges (SENIOR or member with can_edit=True)."""
    if member.role == MemberRole.SENIOR or (member.can_edit and member.is_active):
        return member
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden: edit permissions required",
    )


async def verify_csrf(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Validate CSRF token embedded in state-changing POST forms."""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing CSRF token: no active session",
        )

    form_data = await request.form()
    submitted_csrf = form_data.get("csrf_token")
    if not submitted_csrf or not isinstance(submitted_csrf, str):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing CSRF token",
        )

    if not verify_csrf_token(session_cookie, submitted_csrf, settings.SESSION_SECRET):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing CSRF token",
        )
