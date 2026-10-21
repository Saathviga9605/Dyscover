from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.access import get_assessment_for_user, get_child_for_user
from app.auth.deps import get_current_user, require_roles
from app.core.config import get_settings
from app.database import get_db
from app.ml.service import extract_profile
from app.models import AssessmentSession, User

from .registry import active_research_model
from .research import RESEARCH_LABEL, predict_assessment, research_overview
from .schema import validate_features
from .service import screen_child

router = APIRouter(prefix="/api/screening", tags=["screening"])


def _ensure_research_enabled() -> None:
    # Disabled research mode looks exactly like a route that does not exist.
    if not get_settings().research_demo_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def research_user(user: User = Depends(get_current_user)) -> User:
    """Authenticate first (anonymous -> 401), then require research mode."""
    _ensure_research_enabled()
    return user


def research_admin(user: User = Depends(require_roles("admin"))) -> User:
    _ensure_research_enabled()
    return user


@router.get("/children/{child_id}")
def child_screening(child_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Screening status/result for the child's latest completed assessment (owner or granted educator)."""
    child = get_child_for_user(db, user, child_id, allow_educator=True)
    return screen_child(db, child)


@router.get("/research/children/{child_id}")
def research_child(child_id: UUID, user: User = Depends(research_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Synthetic research predictor: installed model and the child's assessments (owner or granted educator)."""
    child = get_child_for_user(db, user, child_id, allow_educator=True)
    return research_overview(db, child)


@router.post("/research/children/{child_id}/assessments/{assessment_id}/predict")
def research_predict(child_id: UUID, assessment_id: UUID, user: User = Depends(research_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Run the synthetic research model on this assessment's stored game observations."""
    child = get_child_for_user(db, user, child_id, allow_educator=True)
    assessment = get_assessment_for_user(db, user, assessment_id, allow_educator=True)
    if assessment.child_id != child.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment session not found")
    return predict_assessment(db, child, assessment)


@router.get("/research-demo/assessments/{assessment_id}")
def research_demo(assessment_id: UUID, _: User = Depends(research_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Operator view: scores any assessment with the research model. Nothing is stored."""
    if db.get(AssessmentSession, assessment_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment session not found")
    profile = extract_profile(db, assessment_id)
    features = validate_features(profile[0] if profile else {})
    model, _considered = active_research_model()
    outputs = []
    if model is not None:
        outputs.append({"model_id": model.model_id, "model_version": model.version, "research_score": model.model.score([features.vector])[0] if features.ok else None})  # type: ignore[union-attr]
    return {"label": RESEARCH_LABEL, "assessment_id": str(assessment_id), "features_valid": features.ok, "outputs": outputs}
