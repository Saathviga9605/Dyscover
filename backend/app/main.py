from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database import Base, engine, get_db
from app.l10n import L10N_CONTENT_VERSION, locale_for
from app.models import AssessmentSession, AssessmentSummary, ChildProfile, Fixation, GameSession, GazeSample, InteractionEvent, SpeechSession, Trial
from app.gaze.routes import router as gaze_router
from app.schemas import (
    AssessmentCreate,
    AssessmentResponse,
    ChildCreate,
    ChildResponse,
    EventCreate,
    EventResponse,
    GameCreate,
    GameResponse,
    HealthResponse,
    SummaryCreate,
    SummaryResponse,
    TrialCreate,
    TrialResponse,
)
from app.ml.routes import router as ml_router
from app.ml.quality import router as ml_quality_router
from app.personalization.routes import router as personalization_router
from app.remedial.routes import router as remedial_router
from app.speech.routes import router as speech_router

settings = get_settings()
logger = logging.getLogger("dyscover.api")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    yield


def _ensure_sqlite_column(connection, table: str, column: str, ddl: str) -> None:
    columns = {column["name"] for column in inspect(engine).get_columns(table)}
    if column not in columns:
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    if engine.url.get_backend_name() == "sqlite":
        with engine.begin() as connection:
            _ensure_sqlite_column(connection, "speech_sessions", "expected_text", "expected_text TEXT NOT NULL DEFAULT ''")
            _ensure_sqlite_column(connection, "speech_sessions", "features", "features JSON")
            _ensure_sqlite_column(connection, "assessment_sessions", "created_at", "created_at DATETIME")
            _ensure_sqlite_column(connection, "gaze_samples", "quality", "quality VARCHAR(24) DEFAULT 'tracking'")
            _ensure_sqlite_column(connection, "gaze_samples", "provider", "provider VARCHAR(80)")
            _ensure_sqlite_column(connection, "gaze_samples", "viewport_width", "viewport_width INTEGER")
            _ensure_sqlite_column(connection, "gaze_samples", "viewport_height", "viewport_height INTEGER")
            _ensure_sqlite_column(connection, "assessment_sessions", "language", "language VARCHAR(16) DEFAULT 'en'")
            _ensure_sqlite_column(connection, "assessment_sessions", "locale", "locale VARCHAR(16) DEFAULT 'en-US'")
            _ensure_sqlite_column(connection, "assessment_sessions", "content_version", "content_version VARCHAR(16) DEFAULT '1.0'")
            _ensure_sqlite_column(connection, "game_sessions", "language", "language VARCHAR(16) DEFAULT 'en'")
            _ensure_sqlite_column(connection, "game_sessions", "content_version", "content_version VARCHAR(16) DEFAULT '1.0'")
            _ensure_sqlite_column(connection, "trials", "language", "language VARCHAR(16) DEFAULT 'en'")
            _ensure_sqlite_column(connection, "trials", "content_version", "content_version VARCHAR(16) DEFAULT '1.0'")
            _ensure_sqlite_column(connection, "interaction_events", "language", "language VARCHAR(16) DEFAULT 'en'")
            _ensure_sqlite_column(connection, "speech_sessions", "locale", "locale VARCHAR(16) DEFAULT 'en-US'")
            _ensure_sqlite_column(connection, "practice_sessions", "language", "language VARCHAR(16) DEFAULT 'en'")


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["*"], allow_headers=["*"])
app.include_router(ml_router)
app.include_router(ml_quality_router)
app.include_router(personalization_router)
app.include_router(remedial_router)
app.include_router(speech_router)
app.include_router(gaze_router)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    fields = [
        {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    logger.warning("Request validation failed: %s %s -> %s", request.method, request.url.path, fields)
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": exc.errors()})


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=settings.app_version)


@app.get("/api/version", response_model=HealthResponse)
def version() -> HealthResponse:
    return HealthResponse(status="stage-1", version=settings.app_version)


@app.post("/api/children", response_model=ChildResponse, status_code=status.HTTP_201_CREATED)
def create_child(payload: ChildCreate, db: Session = Depends(get_db)) -> ChildProfile:
    child = ChildProfile(**payload.model_dump())
    db.add(child)
    db.commit()
    db.refresh(child)
    return child


@app.get("/api/children/{child_id}", response_model=ChildResponse)
def get_child(child_id: UUID, db: Session = Depends(get_db)) -> ChildProfile:
    child = db.get(ChildProfile, child_id)
    if child is None:
        raise HTTPException(status_code=404, detail="Child profile not found")
    return child


@app.post("/api/assessments", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: AssessmentCreate, db: Session = Depends(get_db)) -> AssessmentSession:
    if db.get(ChildProfile, payload.child_id) is None:
        raise HTTPException(status_code=404, detail="Child profile not found")
    values = payload.model_dump(exclude_none=True)
    # The server canonicalizes locale/content version from the language so
    # persisted records are always interpretable.
    values["locale"] = values.get("locale") or locale_for(values["language"])
    values["content_version"] = values.get("content_version") or L10N_CONTENT_VERSION
    assessment = AssessmentSession(**values)
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


@app.get("/api/assessments/{assessment_id}", response_model=AssessmentResponse)
def get_assessment(assessment_id: UUID, db: Session = Depends(get_db)) -> AssessmentSession:
    assessment = db.get(AssessmentSession, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment session not found")
    return assessment


@app.post("/api/assessments/{assessment_id}/games", response_model=GameResponse, status_code=status.HTTP_201_CREATED)
def create_game(assessment_id: UUID, payload: GameCreate, db: Session = Depends(get_db)) -> GameSession:
    if db.get(AssessmentSession, assessment_id) is None:
        raise HTTPException(status_code=404, detail="Assessment session not found")
    values = payload.model_dump()
    game = GameSession(assessment_session_id=assessment_id, **values)
    db.add(game)
    db.commit()
    db.refresh(game)
    return game


@app.post("/api/games/{game_session_id}/trials", response_model=TrialResponse, status_code=status.HTTP_201_CREATED)
def create_trial(game_session_id: UUID, payload: TrialCreate, db: Session = Depends(get_db)) -> Trial:
    if db.get(GameSession, game_session_id) is None:
        raise HTTPException(status_code=404, detail="Game session not found")
    values = payload.model_dump()
    values["metadata_json"] = values.pop("metadata")
    trial = Trial(game_session_id=game_session_id, **values)
    db.add(trial)
    db.commit()
    db.refresh(trial)
    return trial


@app.post("/api/assessments/{assessment_id}/games/{game_id}/trials", response_model=TrialResponse, status_code=status.HTTP_201_CREATED)
def create_assessment_trial(assessment_id: UUID, game_id: str, payload: TrialCreate, db: Session = Depends(get_db)) -> Trial:
    if db.get(AssessmentSession, assessment_id) is None:
        raise HTTPException(status_code=404, detail="Assessment session not found")
    game = db.scalar(select(GameSession).where(GameSession.assessment_session_id == assessment_id, GameSession.game_id == game_id))
    if game is None:
        game = GameSession(assessment_session_id=assessment_id, game_id=game_id, game_version=payload.game_version, language=payload.language, content_version=payload.content_version)
        db.add(game)
        db.flush()
    values = payload.model_dump()
    values["metadata_json"] = values.pop("metadata")
    trial = Trial(game_session_id=game.id, **values)
    db.add(trial)
    db.commit()
    db.refresh(trial)
    return trial


@app.post("/api/trials/{trial_id}/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(trial_id: UUID, payload: EventCreate, db: Session = Depends(get_db)) -> InteractionEvent:
    if db.get(Trial, trial_id) is None:
        raise HTTPException(status_code=404, detail="Trial not found")
    event = InteractionEvent(trial_id=trial_id, **payload.model_dump(exclude_none=True))
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@app.get("/api/trials/{trial_id}/events", response_model=list[EventResponse])
def list_trial_events(trial_id: UUID, db: Session = Depends(get_db)) -> list[InteractionEvent]:
    if db.get(Trial, trial_id) is None:
        raise HTTPException(status_code=404, detail="Trial not found")
    return list(db.scalars(select(InteractionEvent).where(InteractionEvent.trial_id == trial_id).order_by(InteractionEvent.sequence_number)))


@app.post("/api/assessments/{assessment_id}/summary", response_model=SummaryResponse, status_code=status.HTTP_201_CREATED)
def create_summary(assessment_id: UUID, payload: SummaryCreate, db: Session = Depends(get_db)) -> AssessmentSummary:
    assessment = db.get(AssessmentSession, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment session not found")
    summary = db.scalar(select(AssessmentSummary).where(AssessmentSummary.assessment_id == assessment_id))
    if summary is None:
        summary = AssessmentSummary(assessment_id=assessment_id, summary=payload.model_dump())
        db.add(summary)
    else:
        summary.summary = payload.model_dump()
    assessment.status = "completed"
    db.commit()
    db.refresh(summary)
    return SummaryResponse(id=summary.id, assessment_id=summary.assessment_id, schema_version=summary.schema_version, created_at=summary.created_at, games=payload.games, total_trials=payload.total_trials)


@app.get("/api/children/{child_id}/assessments", response_model=list[AssessmentResponse])
def list_assessments(child_id: UUID, db: Session = Depends(get_db)) -> list[AssessmentSession]:
    if db.get(ChildProfile, child_id) is None:
        raise HTTPException(status_code=404, detail="Child profile not found")
    return list(db.scalars(select(AssessmentSession).where(AssessmentSession.child_id == child_id).order_by(AssessmentSession.created_at.desc(), AssessmentSession.id.desc())))


@app.get("/api/assessments/{assessment_id}/modality-summary")
def assessment_modality_summary(assessment_id: UUID, db: Session = Depends(get_db)) -> dict:
    """Structured per-modality availability for an assessment.

    Reports only observable coverage — whether gaze speech observations were
    recorded and how complete they are. Never synthesizes ability judgments.
    """
    if db.get(AssessmentSession, assessment_id) is None:
        raise HTTPException(status_code=404, detail="Assessment session not found")

    assessment = db.get(AssessmentSession, assessment_id)
    language_context = {
        "language": assessment.language,
        "locale": assessment.locale,
        "content_version": assessment.content_version,
    }

    game_ids = list(db.scalars(select(GameSession.id).where(GameSession.assessment_session_id == assessment_id)))
    trial_ids: list[UUID] = []
    trials = list(db.scalars(select(Trial).where(Trial.game_session_id.in_(game_ids)))) if game_ids else []
    trial_ids = [trial.id for trial in trials]
    trial_count = len(trial_ids)

    if not trial_ids:
        return {
            "assessment_id": str(assessment_id),
            "language": language_context["language"],
            "locale": language_context["locale"],
            "content_version": language_context["content_version"],
            "gaze": {"recorded": False, "calibration_completed": False, "trial_count": 0, "sample_count": 0, "fixation_count": 0, "trial_coverage": 0.0, "aoi_coverage": 0.0},
            "speech": {"recorded": False, "trial_count": 0, "trial_coverage": 0.0, "transcript_available": 0, "response_timing_available": 0, "asr_available": 0},
        }

    gaze_sample_count = int(db.scalar(select(func.count()).select_from(GazeSample).where(GazeSample.trial_id.in_(trial_ids))) or 0)
    fixations = list(db.scalars(select(Fixation).where(Fixation.trial_id.in_(trial_ids))))
    gaze_trial_ids = set(db.scalars(select(GazeSample.trial_id).where(GazeSample.trial_id.in_(trial_ids))))
    gaze_trial_ids.update(db.scalars(select(Fixation.trial_id).where(Fixation.trial_id.in_(trial_ids))))
    calibration_completed = db.scalar(
        select(func.count()).select_from(InteractionEvent).where(
            InteractionEvent.event_type == "CALIBRATION_COMPLETED",
            InteractionEvent.trial_id.in_(trial_ids),
        )
    ) or 0
    calibration_completed = bool(calibration_completed)
    labeled_fixations = sum(1 for fixation in fixations if fixation.target_type)

    speech_sessions = list(db.scalars(select(SpeechSession).where(SpeechSession.assessment_id == assessment_id)))
    speech_trial_ids = {session.trial_id for session in speech_sessions if session.trial_id is not None}
    transcript_available = sum(1 for trial in trials if trial.id in speech_trial_ids and trial.actual_response)
    response_timing_available = sum(1 for trial in trials if trial.id in speech_trial_ids and trial.reaction_time_ms is not None)
    asr_available = sum(1 for session in speech_sessions if isinstance(session.features_json, dict) and "speech_speech_detected" in session.features_json)

    return {
        "assessment_id": str(assessment_id),
        "language": language_context["language"],
        "locale": language_context["locale"],
        "content_version": language_context["content_version"],
        "gaze": {
            "recorded": bool(gaze_sample_count or fixations),
            "calibration_completed": bool(calibration_completed),
            "trial_count": len(gaze_trial_ids),
            "sample_count": gaze_sample_count,
            "fixation_count": len(fixations),
            "trial_coverage": round(len(gaze_trial_ids) / trial_count, 3),
            "aoi_coverage": round(labeled_fixations / len(fixations), 3) if fixations else 0.0,
        },
        "speech": {
            "recorded": bool(speech_sessions),
            "trial_count": len(speech_sessions),
            "trial_coverage": round(len(speech_trial_ids) / trial_count, 3),
            "transcript_available": transcript_available,
            "response_timing_available": response_timing_available,
            "asr_available": asr_available,
        },
    }
