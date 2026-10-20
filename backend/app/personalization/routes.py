"""Stage 5 personalization API routes.

Exposes the four required endpoints (profile, difficulty, recommendations,
progress) plus an optional combined state endpoint.  All responses are
deterministic: the same child_id with the same persisted trials will return
the same results every time.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.access import get_child_for_user
from app.auth.deps import get_current_user
from app.database import get_db
from app.models import User

from . import PERSONALIZATION_ENGINE_VERSION
from .schemas import (
    SkillProfileResponse,
    DifficultyDecisionResponse,
    RecommendationsResponse,
    ProgressResponse,
)
from .service import build_child_profile, build_game_difficulty, build_child_recommendations, build_child_progress


router = APIRouter(prefix="/api/personalization", tags=["personalization"])


def _require_child(db: Session, user: User, child_id: str) -> str:
    """Owner, or an educator the owner granted access to (read-only views)."""
    return str(get_child_for_user(db, user, child_id, allow_educator=True).id)


@router.get("/children/{child_id}/profile", response_model=SkillProfileResponse)
def child_profile(child_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return build_child_profile(db, _require_child(db, user, child_id))


@router.get("/children/{child_id}/difficulty/{game_id}", response_model=DifficultyDecisionResponse)
def child_difficulty(
    child_id: str,
    game_id: str,
    current: int | None = Query(default=None, ge=1, le=5),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return build_game_difficulty(db, _require_child(db, user, child_id), game_id, current_level=current).__dict__


@router.get("/children/{child_id}/recommendations", response_model=RecommendationsResponse)
def child_recommendations(child_id: str, language: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return build_child_recommendations(db, _require_child(db, user, child_id), language=language)


@router.get("/children/{child_id}/progress", response_model=ProgressResponse)
def child_progress(child_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return build_child_progress(db, _require_child(db, user, child_id))