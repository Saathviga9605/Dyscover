from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AssessmentSession, SpeechSession
from .request import ReadingAnalysisRequest, SpeechFeaturesStoreRequest
from .schemas import SpeechFeaturesResponse, SpeechSessionCreate, SpeechSessionResponse, SpeechStatusResponse
from .service import analyze_reading, provider_status

router = APIRouter(prefix="/api/speech", tags=["speech-research"])

@router.get("/status", response_model=SpeechStatusResponse)
def speech_status(): return provider_status()


@router.post("/sessions", response_model=SpeechSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(payload: SpeechSessionCreate, db: Session = Depends(get_db)) -> SpeechSession:
	if db.get(AssessmentSession, payload.session_id) is None:
		raise HTTPException(status_code=404, detail="Assessment session not found")
	speech_session = SpeechSession(assessment_id=payload.session_id, trial_id=payload.trial_id, task_id=payload.task.task_id, expected_text=payload.task.expected_text, language=payload.language, provider=payload.provider, provider_version=payload.provider_version, audio_available=payload.audio_available, duration_ms=payload.duration_ms)
	db.add(speech_session)
	db.commit()
	db.refresh(speech_session)
	return {"id": speech_session.id, "session_id": speech_session.assessment_id, "trial_id": speech_session.trial_id, "task": payload.task, "language": speech_session.language, "provider": speech_session.provider, "provider_version": speech_session.provider_version, "audio_available": speech_session.audio_available, "duration_ms": speech_session.duration_ms, "created_at": speech_session.created_at}


@router.get("/sessions/{speech_session_id}", response_model=SpeechSessionResponse)
def get_session(speech_session_id: UUID, db: Session = Depends(get_db)) -> SpeechSession:
	speech_session = db.get(SpeechSession, speech_session_id)
	if speech_session is None:
		raise HTTPException(status_code=404, detail="Speech session not found")
	return {"id": speech_session.id, "session_id": speech_session.assessment_id, "trial_id": speech_session.trial_id, "task": {"task_id": speech_session.task_id, "expected_text": speech_session.expected_text, "language": speech_session.language}, "language": speech_session.language, "provider": speech_session.provider, "provider_version": speech_session.provider_version, "audio_available": speech_session.audio_available, "duration_ms": speech_session.duration_ms, "created_at": speech_session.created_at}

@router.post("/analyze", response_model=SpeechFeaturesResponse)
def analyze(request: ReadingAnalysisRequest): return analyze_reading(request.task, request.transcript, request.duration_ms)


@router.post("/sessions/{speech_session_id}/features", response_model=SpeechSessionResponse)
def store_features(speech_session_id: UUID, payload: SpeechFeaturesStoreRequest, db: Session = Depends(get_db)):
    speech_session = db.get(SpeechSession, speech_session_id)
    if speech_session is None:
        raise HTTPException(status_code=404, detail="Speech session not found")
    speech_session.features_json = payload.features
    db.commit()
    db.refresh(speech_session)
    return {"id": speech_session.id, "session_id": speech_session.assessment_id, "trial_id": speech_session.trial_id, "task": {"task_id": speech_session.task_id, "expected_text": speech_session.expected_text, "language": speech_session.language}, "language": speech_session.language, "provider": speech_session.provider, "provider_version": speech_session.provider_version, "audio_available": speech_session.audio_available, "duration_ms": speech_session.duration_ms, "created_at": speech_session.created_at}


@router.get("/sessions/{speech_session_id}/features")
def session_features(speech_session_id: UUID, db: Session = Depends(get_db)):
    speech_session = db.get(SpeechSession, speech_session_id)
    if speech_session is None:
        raise HTTPException(status_code=404, detail="Speech session not found")
    return {"speech_session_id": str(speech_session_id), "speech_available": speech_session.features_json is not None, "features": speech_session.features_json or {}}
