"""Dyscover API application.

All routers are mounted exactly once under ``/api``. Schema changes are applied
with Alembic: development runs ``upgrade head`` automatically at startup;
production refuses to start unless the database is already at head.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
import re
import uuid

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.auth.deps import CSRF_HEADER
from app.auth.routes import router as auth_router
from app.assessments.routes import router as assessments_router
from app.chat.routes import router as chat_router
from app.chat.service import provider_status as lexi_status
from app.children.routes import router as children_router
from app.core.config import get_settings
from app.core.migrations import current_revision, ensure_schema_current
from app.core.rate_limit import limiter
from app.database import engine
from app.educator.routes import router as educator_router
from app.gaze.routes import router as gaze_router
from app.ml.quality import router as ml_quality_router
from app.ml.routes import router as ml_router
from app.ml.screening.routes import router as screening_router
from app.personalization.routes import router as personalization_router
from app.privacy.routes import router as privacy_router
from app.remedial.routes import router as remedial_router
from app.schemas import HealthResponse, ReadinessResponse
from app.speech.demo_routes import router as speech_demo_router
from app.speech.routes import router as speech_router

settings = get_settings()
logger = logging.getLogger("dyscover.api")

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
# JSON bodies above this size are rejected before parsing. Audio uploads have
# their own (streamed) limit in the speech demo routes.
MAX_JSON_BODY_BYTES = 2 * 1024 * 1024
_UPLOAD_PATH_PREFIX = "/api/speech/demo/"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    ensure_schema_current(engine, settings.should_auto_migrate)
    yield
    engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def guard_and_annotate(request: Request, call_next):
    incoming = request.headers.get("X-Request-ID", "")
    request_id = incoming if _REQUEST_ID.match(incoming) else uuid.uuid4().hex
    request.state.request_id = request_id

    length = request.headers.get("content-length")
    if length and length.isdigit():
        limit = settings.speech_upload_max_bytes + 64 * 1024 if request.url.path.startswith(_UPLOAD_PATH_PREFIX) else MAX_JSON_BODY_BYTES
        if int(length) > limit:
            return JSONResponse(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, content={"detail": "Request body too large"}, headers={"X-Request-ID": request_id})

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    if request.url.path.startswith("/api/") and "Cache-Control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", CSRF_HEADER],
    expose_headers=["X-Request-ID"],
)

for router in (
    auth_router,
    children_router,
    assessments_router,
    educator_router,
    ml_router,
    ml_quality_router,
    screening_router,
    personalization_router,
    remedial_router,
    speech_router,
    speech_demo_router,
    gaze_router,
    privacy_router,
    chat_router,
):
    app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Submitted values ("input") are deliberately not echoed back or logged.
    errors = [{"loc": list(error.get("loc", ())), "msg": error.get("msg", "Invalid value"), "type": error.get("type", "value_error")} for error in exc.errors()]
    logger.info("Request validation failed: %s %s (%d errors)", request.method, request.url.path, len(errors))
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": errors})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, HTTPException):  # pragma: no cover - handled by FastAPI
        raise exc
    request_id = getattr(request.state, "request_id", None)
    logger.exception("Unhandled error on %s %s (request_id=%s)", request.method, request.url.path, request_id)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred.", "request_id": request_id},
    )


@app.get("/api/health", response_model=HealthResponse, tags=["operations"])
def health() -> HealthResponse:
    """Liveness: the process is up. Does not touch dependencies."""
    return HealthResponse(status="ok", version=settings.app_version)


@app.get("/api/health/ready", response_model=ReadinessResponse, tags=["operations"])
def readiness() -> JSONResponse:
    """Readiness: database reachable and schema migrated. Lexi is reported, not required."""
    database, revision = "ok", None
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        revision = current_revision(engine)
    except Exception:
        logger.exception("Readiness check: database unavailable")
        database = "unavailable"
    lexi = "configured" if lexi_status()["configured"] else "not_configured"
    ready = database == "ok"
    body = ReadinessResponse(status="ready" if ready else "not_ready", version=settings.app_version, database=database, schema_revision=revision, lexi=lexi)
    return JSONResponse(status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE, content=body.model_dump())
