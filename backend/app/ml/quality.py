from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AssessmentSession, GazeSample, SpeechSession, Trial
from .validation import build_quality_report

router = APIRouter(prefix="/api/ml", tags=["ml-research"])

@router.get("/quality")
def quality(db: Session = Depends(get_db)):
    sessions = list(db.scalars(select(AssessmentSession)))
    trials = list(db.scalars(select(Trial)))
    gaze = {str(sample.trial_id) for sample in db.scalars(select(GazeSample))}
    speech = {str(speech.trial_id) for speech in db.scalars(select(SpeechSession)) if speech.trial_id is not None}
    return build_quality_report(sessions, trials, gaze, speech)
