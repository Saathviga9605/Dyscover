from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database import Base, engine, get_db
from app.models import AssessmentSession, AssessmentSummary, ChildProfile, GameSession, InteractionEvent, Trial
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
from app.speech.routes import router as speech_router

settings = get_settings()
logger = logging.getLogger("dyscover.api")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    yield


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    if engine.url.get_backend_name() == "sqlite":
        columns = {column["name"] for column in inspect(engine).get_columns("speech_sessions")}
        if "expected_text" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE speech_sessions ADD COLUMN expected_text TEXT NOT NULL DEFAULT ''"))


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["*"], allow_headers=["*"])
app.include_router(ml_router)
app.include_router(ml_quality_router)
app.include_router(speech_router)

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
    assessment = AssessmentSession(**payload.model_dump())
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
    game = GameSession(assessment_session_id=assessment_id, game_id=payload.game_id, game_version=payload.game_version)
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
        game = GameSession(assessment_session_id=assessment_id, game_id=game_id, game_version=payload.game_version)
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
