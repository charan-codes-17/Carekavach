from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.clock import Clock, SystemClock
from app.config import Settings, get_settings
from app.dependencies import (
    SESSION_COOKIE_NAME,
    get_clock,
    get_current_member,
    get_repository,
)
from app.models import Member, MemberRole
from app.repositories import BaseRepository, FirestoreRepository, MemoryRepository
from app.routes.appointments import router as appointments_router
from app.routes.audit import router as audit_router
from app.routes.auth import router as auth_router
from app.routes.doses import router as doses_router
from app.routes.medications import router as medications_router
from app.routes.members import router as members_router
from app.routes.setup import router as setup_router
from app.routes.tasks import router as tasks_router
from app.services.adherence import get_today_slots
from app.services.auth import generate_csrf_token


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and repository lifecycle."""
    settings = get_settings()
    if settings.USE_FIRESTORE:
        app.state.repository = FirestoreRepository(
            project_id=settings.GOOGLE_CLOUD_PROJECT,
            credentials_json=settings.FIREBASE_CREDENTIALS_JSON,
        )
    else:
        app.state.repository = MemoryRepository()

    app.state.clock = SystemClock()
    yield


app = FastAPI(
    title="CareKavach",
    description="Elderly Care and Medication Management Platform",
    lifespan=lifespan,
)

# Static files and template engine
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Register routers
app.include_router(setup_router)
app.include_router(auth_router)
app.include_router(members_router)
app.include_router(medications_router)
app.include_router(doses_router)
app.include_router(appointments_router)
app.include_router(audit_router)
app.include_router(tasks_router)


@app.get("/health", response_class=JSONResponse)
async def health_check() -> dict[str, str]:
    """Lightweight health check probe for container runners."""
    return {"status": "healthy", "service": "carekavach"}


@app.get("/health/db", response_class=JSONResponse)
async def database_health_check(
    repo: Annotated[BaseRepository, Depends(get_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    """Verify database read/write/delete readiness."""
    db_type = "firestore" if settings.USE_FIRESTORE else "memory"
    try:
        ok = await repo.ping_db()
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"status": "unhealthy", "database": db_type, "error": "Ping failed"},
            )
        return {"status": "healthy", "database": db_type, "write_read_delete": "ok"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unhealthy", "database": db_type, "error": str(exc)},
        ) from exc


@app.get("/", response_class=HTMLResponse)
async def root_view(
    request: Request,
    current_member: Annotated[Member, Depends(get_current_member)],
    repo: Annotated[BaseRepository, Depends(get_repository)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    """Role-tailored dashboard.

    SENIOR/CARETAKER: next pending dose hero card plus today's slot list.
    FAMILY: today's adherence counts and upcoming appointments, never private medications.
    """
    tz = ZoneInfo(settings.DEFAULT_TIMEZONE)
    now = clock.now_utc()
    today_date_str = now.astimezone(tz).strftime("%Y-%m-%d")

    is_family = current_member.role == MemberRole.FAMILY
    all_meds = await repo.list_medications("default_profile", active_only=True)
    meds = [m for m in all_meds if not m.is_private] if is_family else all_meds

    logs = await repo.list_dose_logs("default_profile", today_date_str, today_date_str)
    slots = get_today_slots(meds, logs, now, tz)

    next_dose = next((slot for slot in slots if slot.status == "PENDING"), None)
    adherence = {
        "taken": sum(1 for slot in slots if slot.status == "TAKEN"),
        "skipped": sum(1 for slot in slots if slot.status == "SKIPPED"),
        "missed": sum(1 for slot in slots if slot.status == "MISSED"),
        "pending": sum(1 for slot in slots if slot.status == "PENDING"),
    }

    upcoming = await repo.list_appointments("default_profile", upcoming_only=True, now=now)
    appointments = [
        {
            "doctor_name": appt.doctor_name,
            "specialty": appt.specialty,
            "location": appt.location,
            "formatted_datetime": appt.appointment_datetime.astimezone(tz)
            .strftime("%a, %d %b %Y at %I:%M %p")
            .replace(" 0", " "),
        }
        for appt in upcoming[:3]
    ]

    session_cookie = request.cookies.get(SESSION_COOKIE_NAME, "")
    csrf_token = generate_csrf_token(session_cookie, settings.SESSION_SECRET)
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "request": request,
            "current_member": current_member,
            "next_dose": next_dose,
            "slots": slots,
            "adherence": adherence,
            "appointments": appointments,
            "today_date": today_date_str,
            "csrf_token": csrf_token,
        },
    )
