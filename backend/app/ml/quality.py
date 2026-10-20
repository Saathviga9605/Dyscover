from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import require_roles
from app.database import get_db
from app.models import AssessmentSession, GazeSample, SpeechSession, Trial, User
from .validation import build_quality_report

router = APIRouter(prefix="/api/ml", tags=["ml-research"])


@router.get("/quality")
def quality(_: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    """Platform-wide data-quality report. Aggregates every child's data, so it is
    restricted to operator (``admin``) accounts, which cannot self-register."""
    sessions = list(db.scalars(select(AssessmentSession)))
    trials = list(db.scalars(select(Trial)))
    gaze = {str(trial_id) for trial_id in db.scalars(select(GazeSample.trial_id).distinct())}
    speech = {str(speech.trial_id) for speech in db.scalars(select(SpeechSession)) if speech.trial_id is not None}
    return build_quality_report(sessions, trials, gaze, speech)
