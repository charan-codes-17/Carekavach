from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.clock import SystemClock
from app.config import Settings, get_settings
from app.dependencies import (
    SESSION_COOKIE_NAME,
    get_current_member,
    get_repository,
)
from app.models import Member
from app.repositories import BaseRepository, FirestoreRepository, MemoryRepository
from app.routes.appointments import router as appointments_router
from app.routes.audit import router as audit_router
from app.routes.auth import router as auth_router
from app.routes.doses import router as doses_router
from app.routes.medications import router as medications_router
from app.routes.members import router as members_router
from app.routes.setup import router as setup_router
from app.routes.tasks import router as tasks_router
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
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    """Root view serving accessible member placeholder dashboard."""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME, "")
    csrf_token = generate_csrf_token(session_cookie, settings.SESSION_SECRET)
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "request": request,
            "current_member": current_member,
            "csrf_token": csrf_token,
        },
    )
