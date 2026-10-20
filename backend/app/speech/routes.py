from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.access import get_assessment_for_user, get_speech_session_for_user, get_trial_for_user
from app.auth.deps import get_current_user
from app.database import get_db
from app.l10n import locale_for
from app.models import SpeechSession, User
from .request import ReadingAnalysisRequest, SpeechFeaturesStoreRequest
from .schemas import SpeechFeaturesResponse, SpeechSessionCreate, SpeechSessionResponse, SpeechStatusResponse
from .service import analyze_reading, provider_status

router = APIRouter(prefix="/api/speech", tags=["speech-research"])


def _session_response(speech_session: SpeechSession, task: dict | None = None) -> dict:
    return {
        "id": speech_session.id,
        "session_id": speech_session.assessment_id,
        "trial_id": speech_session.trial_id,
        "task": task or {"task_id": speech_session.task_id, "expected_text": speech_session.expected_text, "language": speech_session.language},
        "language": speech_session.language,
        "locale": speech_session.locale,
        "provider": speech_session.provider,
        "provider_version": speech_session.provider_version,
        "audio_available": speech_session.audio_available,
        "duration_ms": speech_session.duration_ms,
        "created_at": speech_session.created_at,
    }


@router.get("/status", response_model=SpeechStatusResponse)
def speech_status():
    return provider_status()


@router.post("/sessions", response_model=SpeechSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(payload: SpeechSessionCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    assessment = get_assessment_for_user(db, user, payload.session_id)
    if payload.trial_id is not None:
        trial = get_trial_for_user(db, user, payload.trial_id)
        if trial.game_session.assessment_session_id != assessment.id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="trial_id does not belong to this assessment session")
    speech_session = SpeechSession(
        assessment_id=assessment.id,
        trial_id=payload.trial_id,
        task_id=payload.task.task_id,
        expected_text=payload.task.expected_text,
        language=payload.language,
        locale=payload.locale or locale_for(payload.language),
        provider=payload.provider,
        provider_version=payload.provider_version,
        # The platform never stores raw audio; this flag only records whether
        # audio was captured client-side for transcription.
        audio_available=payload.audio_available,
        duration_ms=payload.duration_ms,
    )
    db.add(speech_session)
    db.commit()
    db.refresh(speech_session)
    return _session_response(speech_session, payload.task.model_dump())


@router.get("/sessions/{speech_session_id}", response_model=SpeechSessionResponse)
def get_session(speech_session_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return _session_response(get_speech_session_for_user(db, user, speech_session_id))


@router.post("/analyze", response_model=SpeechFeaturesResponse)
def analyze(request: ReadingAnalysisRequest, _: User = Depends(get_current_user)):
    return analyze_reading(request.task, request.transcript, request.duration_ms)


@router.post("/sessions/{speech_session_id}/features", response_model=SpeechSessionResponse)
def store_features(speech_session_id: UUID, payload: SpeechFeaturesStoreRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    speech_session = get_speech_session_for_user(db, user, speech_session_id)
    speech_session.features_json = payload.features
    db.commit()
    db.refresh(speech_session)
    return _session_response(speech_session)


@router.get("/sessions/{speech_session_id}/features")
def session_features(speech_session_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    speech_session = get_speech_session_for_user(db, user, speech_session_id)
    return {
        "speech_session_id": str(speech_session.id),
        "speech_available": speech_session.features_json is not None,
        "features": speech_session.features_json or {},
    }
