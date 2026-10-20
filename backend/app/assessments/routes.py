"""Assessment sessions, game sessions, trials, events and summaries.

All endpoints require authentication and resolve ownership through the child
profile (``app.access``). Trial and event writes are idempotent so the
browser's offline retry queue cannot create duplicates.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.access import get_assessment_for_user, get_child_for_user, get_game_session_for_user, get_trial_for_user
from app.assessments.scoring import SCORING_CLIENT, SCORING_SERVER, InvalidTrial, score_trial
from app.audit import AuditEventType, AuditLogger
from app.auth.deps import get_current_user
from app.core.time import utcnow
from app.database import get_db
from app.l10n import L10N_CONTENT_VERSION, locale_for
from app.models import (
    AssessmentSession,
    AssessmentSummary,
    Fixation,
    GameSession,
    GazeSample,
    InteractionEvent,
    SpeechSession,
    Trial,
    User,
)
from app.schemas import (
    AssessmentCreate,
    AssessmentResponse,
    EventCreate,
    EventResponse,
    GameCreate,
    GameResponse,
    SummaryCreate,
    SummaryResponse,
    TrialCreate,
    TrialResponse,
)

router = APIRouter(prefix="/api", tags=["assessments"])


@router.post("/assessments", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: AssessmentCreate, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AssessmentSession:
    child = get_child_for_user(db, user, payload.child_id)
    values = payload.model_dump(exclude_none=True)
    # The server canonicalizes locale/content version from the language so
    # persisted records are always interpretable.
    values["locale"] = locale_for(values["language"])
    values["content_version"] = values.get("content_version") or L10N_CONTENT_VERSION
    values["child_id"] = child.id
    assessment = AssessmentSession(**values)
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    AuditLogger(request).log(AuditEventType.ASSESSMENT_CREATE, user_id=str(user.id), resource_type="assessment", resource_id=str(assessment.id))
    return assessment


@router.get("/assessments/{assessment_id}", response_model=AssessmentResponse)
def get_assessment(assessment_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AssessmentSession:
    return get_assessment_for_user(db, user, assessment_id)


@router.get("/children/{child_id}/assessments", response_model=list[AssessmentResponse])
def list_assessments(
    child_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AssessmentSession]:
    child = get_child_for_user(db, user, child_id)
    return list(
        db.scalars(
            select(AssessmentSession)
            .where(AssessmentSession.child_id == child.id)
            .order_by(AssessmentSession.created_at.desc(), AssessmentSession.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def _get_or_create_game(db: Session, assessment: AssessmentSession, game_id: str, game_version: str, language: str, content_version: str) -> GameSession:
    game = db.scalar(select(GameSession).where(GameSession.assessment_session_id == assessment.id, GameSession.game_id == game_id))
    if game is None:
        game = GameSession(
            assessment_session_id=assessment.id,
            game_id=game_id,
            game_version=game_version,
            language=language,
            content_version=content_version,
            started_at=utcnow(),
        )
        db.add(game)
        db.flush()
    return game


@router.post("/assessments/{assessment_id}/games", response_model=GameResponse, status_code=status.HTTP_201_CREATED)
def create_game(assessment_id: UUID, payload: GameCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> GameSession:
    assessment = get_assessment_for_user(db, user, assessment_id)
    game = _get_or_create_game(db, assessment, payload.game_id, payload.game_version, payload.language, payload.content_version)
    db.commit()
    db.refresh(game)
    return game


def _reject_if_completed(assessment: AssessmentSession) -> None:
    if assessment.status == "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Assessment session is already completed")


def _insert_trial(db: Session, game: GameSession, payload: TrialCreate, response: Response) -> Trial:
    existing = db.scalar(select(Trial).where(Trial.game_session_id == game.id, Trial.trial_number == payload.trial_number))
    if existing is not None:
        # Idempotent retry of the same trial (offline queue / double submit).
        response.status_code = status.HTTP_200_OK
        return existing

    values = payload.model_dump()
    metadata: dict[str, Any] = dict(values.pop("metadata") or {})
    unscored = payload.actual_response is None and payload.correctness is None
    try:
        scored = None if unscored else score_trial(game.game_id, payload.stimulus, payload.expected_response, payload.actual_response)
    except InvalidTrial as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    if unscored:
        # No response and no claimed outcome: this trial carries no accuracy evidence.
        values["score"] = 0.0
        metadata["scoring"] = "unscored"
    elif scored is not None:
        if scored.correct != payload.correctness or abs(scored.score - payload.score) > 1e-6:
            metadata["client_reported"] = {"correctness": payload.correctness, "score": payload.score}
        values["correctness"] = scored.correct
        values["score"] = scored.score
        metadata["scoring"] = SCORING_SERVER
    else:
        metadata["scoring"] = SCORING_CLIENT
    trial = Trial(game_session_id=game.id, metadata_json=metadata, **values)
    db.add(trial)
    assessment = game.assessment
    if assessment.started_at is None:
        assessment.started_at = utcnow()
        assessment.status = "in_progress"
    try:
        db.commit()
    except IntegrityError:
        # Concurrent duplicate: the unique (game_session_id, trial_number) index won.
        db.rollback()
        existing = db.scalar(select(Trial).where(Trial.game_session_id == game.id, Trial.trial_number == payload.trial_number))
        if existing is None:
            raise
        response.status_code = status.HTTP_200_OK
        return existing
    db.refresh(trial)
    return trial


@router.post("/games/{game_session_id}/trials", response_model=TrialResponse, status_code=status.HTTP_201_CREATED)
def create_trial(game_session_id: UUID, payload: TrialCreate, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Trial:
    game = get_game_session_for_user(db, user, game_session_id)
    _reject_if_completed(game.assessment)
    return _insert_trial(db, game, payload, response)


@router.post("/assessments/{assessment_id}/games/{game_id}/trials", response_model=TrialResponse, status_code=status.HTTP_201_CREATED)
def create_assessment_trial(assessment_id: UUID, game_id: str, payload: TrialCreate, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Trial:
    assessment = get_assessment_for_user(db, user, assessment_id)
    _reject_if_completed(assessment)
    try:
        GameCreate(game_id=game_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown game {game_id!r}")
    game = _get_or_create_game(db, assessment, game_id, payload.game_version, payload.language, payload.content_version)
    return _insert_trial(db, game, payload, response)


@router.post("/trials/{trial_id}/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(trial_id: UUID, payload: EventCreate, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> InteractionEvent:
    trial = get_trial_for_user(db, user, trial_id)
    assessment = trial.game_session.assessment
    if payload.sequence_number is not None:
        existing = db.scalar(
            select(InteractionEvent).where(
                InteractionEvent.trial_id == trial.id,
                InteractionEvent.sequence_number == payload.sequence_number,
                InteractionEvent.event_type == payload.event_type,
            )
        )
        if existing is not None:
            response.status_code = status.HTTP_200_OK
            return existing
    values = payload.model_dump(exclude_none=True)
    # Events always belong to the trial's own assessment; a client-supplied
    # session_id that points elsewhere is ignored.
    values["session_id"] = assessment.id
    event = InteractionEvent(trial_id=trial.id, **values)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/trials/{trial_id}/events", response_model=list[EventResponse])
def list_trial_events(trial_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[InteractionEvent]:
    trial = get_trial_for_user(db, user, trial_id)
    return list(db.scalars(select(InteractionEvent).where(InteractionEvent.trial_id == trial.id).order_by(InteractionEvent.sequence_number, InteractionEvent.timestamp)))


@router.post("/assessments/{assessment_id}/summary", response_model=SummaryResponse, status_code=status.HTTP_201_CREATED)
def create_summary(assessment_id: UUID, payload: SummaryCreate, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SummaryResponse:
    assessment = get_assessment_for_user(db, user, assessment_id)
    # Totals are counted from persisted trials, not taken from the client.
    game_ids = list(db.scalars(select(GameSession.id).where(GameSession.assessment_session_id == assessment.id)))
    persisted_trials = int(db.scalar(select(func.count()).select_from(Trial).where(Trial.game_session_id.in_(game_ids))) or 0) if game_ids else 0
    stored = {"games": payload.games, "total_trials": persisted_trials, "client_total_trials": payload.total_trials}
    summary = db.scalar(select(AssessmentSummary).where(AssessmentSummary.assessment_id == assessment.id))
    if summary is None:
        summary = AssessmentSummary(assessment_id=assessment.id, summary=stored)
        db.add(summary)
    else:
        summary.summary = stored
    assessment.status = "completed"
    assessment.completed_at = assessment.completed_at or utcnow()
    db.commit()
    db.refresh(summary)
    AuditLogger(request).log(AuditEventType.ASSESSMENT_COMPLETE, user_id=str(user.id), resource_type="assessment", resource_id=str(assessment.id))
    return SummaryResponse(
        id=summary.id,
        assessment_id=summary.assessment_id,
        schema_version=summary.schema_version,
        created_at=summary.created_at,
        games=payload.games,
        total_trials=persisted_trials,
    )


@router.get("/assessments/{assessment_id}/modality-summary")
def assessment_modality_summary(assessment_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Structured per-modality availability for an assessment.

    Reports only observable coverage — whether gaze/speech observations were
    recorded and how complete they are. Never synthesizes ability judgments.
    Unavailable coverage is reported as ``null`` rather than 0.
    """
    assessment = get_assessment_for_user(db, user, assessment_id)
    language_context = {"language": assessment.language, "locale": assessment.locale, "content_version": assessment.content_version}
    game_ids = list(db.scalars(select(GameSession.id).where(GameSession.assessment_session_id == assessment.id)))
    trials = list(db.scalars(select(Trial).where(Trial.game_session_id.in_(game_ids)))) if game_ids else []
    trial_ids = [trial.id for trial in trials]
    trial_count = len(trial_ids)

    if not trial_ids:
        return {
            "assessment_id": str(assessment.id),
            **language_context,
            "gaze": {"recorded": False, "calibration_completed": False, "trial_count": 0, "sample_count": 0, "fixation_count": 0, "trial_coverage": None, "aoi_coverage": None},
            "speech": {"recorded": False, "trial_count": 0, "trial_coverage": None, "transcript_available": 0, "response_timing_available": 0, "asr_available": 0},
        }

    gaze_sample_count = int(db.scalar(select(func.count()).select_from(GazeSample).where(GazeSample.trial_id.in_(trial_ids))) or 0)
    fixations = list(db.scalars(select(Fixation).where(Fixation.trial_id.in_(trial_ids))))
    gaze_trial_ids = set(db.scalars(select(GazeSample.trial_id).where(GazeSample.trial_id.in_(trial_ids))))
    gaze_trial_ids.update(fixation.trial_id for fixation in fixations)
    calibration_completed = bool(
        db.scalar(
            select(func.count()).select_from(InteractionEvent).where(
                InteractionEvent.event_type == "CALIBRATION_COMPLETED",
                InteractionEvent.trial_id.in_(trial_ids),
            )
        )
    )
    labeled_fixations = sum(1 for fixation in fixations if fixation.target_type)

    speech_sessions = list(db.scalars(select(SpeechSession).where(SpeechSession.assessment_id == assessment.id)))
    speech_trial_ids = {session.trial_id for session in speech_sessions if session.trial_id is not None}
    transcript_available = sum(1 for trial in trials if trial.id in speech_trial_ids and trial.actual_response)
    response_timing_available = sum(1 for trial in trials if trial.id in speech_trial_ids and trial.reaction_time_ms is not None)
    asr_available = sum(1 for session in speech_sessions if isinstance(session.features_json, dict) and "speech_speech_detected" in session.features_json)

    return {
        "assessment_id": str(assessment.id),
        **language_context,
        "gaze": {
            "recorded": bool(gaze_sample_count or fixations),
            "calibration_completed": calibration_completed,
            "trial_count": len(gaze_trial_ids),
            "sample_count": gaze_sample_count,
            "fixation_count": len(fixations),
            "trial_coverage": round(len(gaze_trial_ids) / trial_count, 3),
            "aoi_coverage": round(labeled_fixations / len(fixations), 3) if fixations else None,
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
