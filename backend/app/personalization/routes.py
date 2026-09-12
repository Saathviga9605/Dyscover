"""Stage 5 personalization API routes.

Exposes the four required endpoints (profile, difficulty, recommendations,
progress) plus an optional combined state endpoint.  All responses are
deterministic: the same child_id with the same persisted trials will return
the same results every time.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ChildProfile

from . import PERSONALIZATION_ENGINE_VERSION
from .schemas import (
    SkillProfileResponse,
    DifficultyDecisionResponse,
    RecommendationsResponse,
    ProgressResponse,
)
from .service import build_child_profile, build_game_difficulty, build_child_recommendations, build_child_progress


router = APIRouter(prefix="/api/personalization", tags=["personalization"])


def _require_child(db: Session, child_id: str) -> ChildProfile:
    try:
        child_uuid = UUID(child_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Child not found")
    child = db.get(ChildProfile, child_uuid)
    if child is None:
        raise HTTPException(status_code=404, detail="Child not found")
    return child


@router.get("/children/{child_id}/profile", response_model=SkillProfileResponse)
def child_profile(child_id: str, db: Session = Depends(get_db)):
    _require_child(db, child_id)
    return build_child_profile(db, child_id)


@router.get("/children/{child_id}/difficulty/{game_id}", response_model=DifficultyDecisionResponse)
def child_difficulty(
    child_id: str,
    game_id: str,
    current: int | None = None,
    db: Session = Depends(get_db),
):
    _require_child(db, child_id)
    return build_game_difficulty(db, child_id, game_id, current_level=current).__dict__


@router.get("/children/{child_id}/recommendations", response_model=RecommendationsResponse)
def child_recommendations(child_id: str, language: str | None = None, db: Session = Depends(get_db)):
    _require_child(db, child_id)
    return build_child_recommendations(db, child_id, language=language)


@router.get("/children/{child_id}/progress", response_model=ProgressResponse)
def child_progress(child_id: str, db: Session = Depends(get_db)):
    _require_child(db, child_id)
    return build_child_progress(db, child_id)