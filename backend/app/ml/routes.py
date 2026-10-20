from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.access import get_assessment_for_user
from app.auth.deps import get_current_user
from app.database import get_db
from app.models import User
from .registry import get_model, list_models
from .schemas import ModelInfo, PredictionResponse, ScreeningProfileResponse
from .service import extract_profile

router = APIRouter(prefix="/api/ml", tags=["ml-research"])


def _features_response(session_id: UUID, db: Session) -> dict:
    result = extract_profile(db, session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Assessment session not found")
    features, quality, _ = result
    return {"session_id": session_id, "feature_schema_version": "1.0", "feature_extractor_version": "1.0", "features": features, "quality": quality}


@router.post("/features/session/{session_id}")
def create_features(session_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_assessment_for_user(db, user, session_id)
    return _features_response(session_id, db)


@router.get("/features/session/{session_id}")
def get_features(session_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_assessment_for_user(db, user, session_id)
    return _features_response(session_id, db)


@router.get("/profile/session/{session_id}", response_model=ScreeningProfileResponse)
def get_profile(session_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_assessment_for_user(db, user, session_id)
    result = extract_profile(db, session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Assessment session not found")
    return result[2]


@router.post("/predict/session/{session_id}", response_model=PredictionResponse)
def predict(session_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Predictive inference is deliberately unavailable: no model has been
    validated on real, appropriately labelled data (docs/readiness/ai-ml-validation.md)."""
    get_assessment_for_user(db, user, session_id)
    return {
        "status": "unavailable",
        "model_state": "unavailable",
        "mode": "UNAVAILABLE",
        "model": None,
        "prediction": None,
        "limitations": [
            "ML prediction is unavailable because no validated trained model is registered.",
            "Observed activity results remain available.",
        ],
    }


@router.get("/models", response_model=list[ModelInfo])
def models(_: User = Depends(get_current_user)):
    return list_models()


@router.get("/models/{model_id}", response_model=ModelInfo)
def model(model_id: str, _: User = Depends(get_current_user)):
    found = get_model(model_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return found
