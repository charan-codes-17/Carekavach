from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import Settings, get_settings
from app.dependencies import (
    SESSION_COOKIE_NAME,
    get_repository,
    require_role,
)
from app.models import Member, MemberRole
from app.repositories import BaseRepository
from app.services.auth import generate_csrf_token

router = APIRouter(prefix="/audit", tags=["Audit"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def audit_log_view(
    request: Request,
    current_member: Annotated[
        Member,
        Depends(require_role(MemberRole.SENIOR, MemberRole.CARETAKER)),
    ],
    repo: Annotated[BaseRepository, Depends(get_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    """Chronological audit log view for Senior and Caretakers.

    Family role is forbidden (403). Audit entries never expose passcodes or secret hashes.
    """
    entries = await repo.list_audit_entries("default_profile", limit=100)
    tz = ZoneInfo(settings.DEFAULT_TIMEZONE)

    formatted_entries = []
    for entry in entries:
        local_ts = entry.timestamp.astimezone(tz)
        formatted_entries.append(
            {
                "id": entry.id,
                "action": entry.action.replace("_", " ").title(),
                "actor_name": entry.actor_name,
                "formatted_time": local_ts.strftime("%d %b %Y, %I:%M %p").replace(" 0", " "),
                "details": entry.details,
            }
        )

    session_cookie = request.cookies.get(SESSION_COOKIE_NAME, "")
    csrf_token = generate_csrf_token(session_cookie, settings.SESSION_SECRET)

    return templates.TemplateResponse(
        request=request,
        name="audit_log.html",
        context={
            "request": request,
            "current_member": current_member,
            "audit_entries": formatted_entries,
            "csrf_token": csrf_token,
        },
    )
