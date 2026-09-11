"""Orchestrates personalization computation from persisted database state.

Aggregation is child-scoped across completed assessments.  A single
combined ``state`` helper is provided alongside the four endpoint-scoped
helpers (profile, difficulty, recommendations, progress).
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AssessmentSession, GameSession, Trial

from . import PERSONALIZATION_ENGINE_VERSION, PERSONALIZATION_SCHEMA_VERSION, MODE
from .config import PERSONALIZATION_CONFIG, config_summary
from .difficulty import DifficultyDecision
from .domains import DEFAULT_GAME_ORDER
from .recommendations import build_recommendations
from .progress import build_progress
from .skills import build_profile


@dataclass
class ObservedTrial:
    """Minimal view of a persisted Trial joined with its game id.

    The pure personalization functions consume this interface only, keeping
    them decoupled from ORM specifics while staying fully deterministic.
    """

    game_id: str
    correctness: bool | None
    reaction_time_ms: float | None = None
    completed_at: datetime | None = None
    started_at: datetime | None = None


def _all_game_sessions(db: Session, child_id: str) -> list[GameSession]:
    return list(
        db.scalars(
            select(GameSession)
            .join(AssessmentSession)
            .where(AssessmentSession.child_id == UUID(child_id))
        )
    )


def _observed_trials(db: Session, child_id: str) -> list[ObservedTrial]:
    game_sessions = _all_game_sessions(db, child_id)
    game_by_id = {gs.id: gs.game_id for gs in game_sessions}
    if not game_by_id:
        return []
    trials = list(db.scalars(select(Trial).where(Trial.game_session_id.in_(game_by_id.keys()))))
    return [
        ObservedTrial(
            game_id=game_by_id[trial.game_session_id],
            correctness=trial.correctness,
            reaction_time_ms=trial.reaction_time_ms,
            completed_at=trial.completed_at,
            started_at=trial.started_at,
        )
        for trial in trials
    ]


def _assessments_and_trials(db: Session, child_id: str) -> list[tuple[AssessmentSession, list[ObservedTrial]]]:
    assessments = list(
        db.scalars(
            select(AssessmentSession)
            .where(AssessmentSession.child_id == UUID(child_id))
        )
    )
    result = []
    for assessment in assessments:
        game_sessions = list(
            db.scalars(
                select(GameSession).where(GameSession.assessment_session_id == assessment.id)
            )
        )
        game_by_id = {gs.id: gs.game_id for gs in game_sessions}
        assessment_trials = []
        for gs in game_sessions:
            stored_trials = db.scalars(select(Trial).where(Trial.game_session_id == gs.id))
            assessment_trials.extend(
                ObservedTrial(
                    game_id=gs.game_id,
                    correctness=t.correctness,
                    reaction_time_ms=t.reaction_time_ms,
                    completed_at=t.completed_at,
                    started_at=t.started_at,
                )
                for t in stored_trials
            )
        result.append((assessment, sorted(assessment_trials, key=lambda t: t.started_at or datetime.min.replace(tzinfo=timezone.utc))))
    return sorted(
        result,
        key=lambda x: (
            x[0].completed_at or x[0].created_at or datetime.min.replace(tzinfo=timezone.utc),
            x[0].id,
        ),
    )


def _child_trials(db: Session, child_id: str) -> list[ObservedTrial]:
    return _observed_trials(db, child_id)


def build_child_profile(db: Session, child_id: str) -> dict:
    trials = _child_trials(db, child_id)
    skills = build_profile(trials, PERSONALIZATION_CONFIG)
    return {
        "child_id": child_id,
        "engine_version": PERSONALIZATION_ENGINE_VERSION,
        "schema_version": PERSONALIZATION_SCHEMA_VERSION,
        "config_summary": config_summary(),
        "mode": MODE,
        "skills": [skill.to_dict() for skill in skills],
    }


def build_game_difficulty(db: Session, child_id: str, game_id: str, current_level: int | None = None) -> DifficultyDecision:
    from .difficulty import decide
    trials = _child_trials(db, child_id)
    game_trials = [t for t in trials if t.game_id == game_id]
    return decide(game_id, game_trials, PERSONALIZATION_CONFIG.difficulty, current_level)


def build_child_recommendations(db: Session, child_id: str) -> dict:
    trials = _child_trials(db, child_id)
    skills = build_profile(trials, PERSONALIZATION_CONFIG)
    recommendations = build_recommendations(skills, PERSONALIZATION_CONFIG)
    for rec in recommendations:
        if rec.game_id is not None:
            decision = build_game_difficulty(db, child_id, rec.game_id)
            rec.suggested_difficulty = decision.level
    return {
        "child_id": child_id,
        "engine_version": PERSONALIZATION_ENGINE_VERSION,
        "mode": MODE,
        "recommendations": [rec.__dict__ for rec in recommendations],
    }


def build_child_progress(db: Session, child_id: str) -> dict:
    at = _assessments_and_trials(db, child_id)
    progress = build_progress(at, PERSONALIZATION_CONFIG)
    progress.update(child_id=child_id, engine_version=PERSONALIZATION_ENGINE_VERSION, mode=MODE)
    return progress


def build_child_state(db: Session, child_id: str) -> dict:
    """Single combined view: profile + recommendations + difficulty + progress."""
    profile = build_child_profile(db, child_id)
    recommendations = build_child_recommendations(db, child_id)
    difficulty = {
        game_id: build_game_difficulty(db, child_id, game_id).__dict__
        for game_id in DEFAULT_GAME_ORDER
    }
    progress = build_child_progress(db, child_id)
    return {
        "child_id": child_id,
        "engine_version": PERSONALIZATION_ENGINE_VERSION,
        "schema_version": PERSONALIZATION_SCHEMA_VERSION,
        "mode": MODE,
        "profile": profile,
        "recommendations": recommendations,
        "difficulty": difficulty,
        "progress": progress,
    }