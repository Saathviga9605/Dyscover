"""Reading-difficulty screening for a child's latest completed assessment.

Always returns the observation summary; returns a model output only when an
eligible model exists and the assessment satisfies that model's input
requirements. Every other outcome is an explicit status with reason codes.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.ml.service import extract_profile
from app.models import AssessmentSession, ChildProfile, GameSession, ScreeningResult, SpeechSession, Trial
from app.personalization.service import build_child_profile

from .registry import RegisteredModel, active_model
from .schema import SCREENING_SCHEMA_VERSION, TARGET_DEFINITION, validate_features

logger = logging.getLogger("dyscover.screening")

MIN_TRIALS_PER_DOMAIN_SUMMARY = 3


def _latest_completed(db: Session, child: ChildProfile) -> tuple[AssessmentSession | None, bool]:
    completed = db.scalar(
        select(AssessmentSession)
        .where(AssessmentSession.child_id == child.id, AssessmentSession.status == "completed")
        .order_by(AssessmentSession.completed_at.desc(), AssessmentSession.created_at.desc())
        .limit(1)
    )
    any_started = db.scalar(select(AssessmentSession.id).where(AssessmentSession.child_id == child.id).limit(1)) is not None
    return completed, any_started


def _observations(db: Session, child: ChildProfile, assessment: AssessmentSession | None) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "scored_trials": 0,
        "unscored_trials": 0,
        "games_played": [],
        "domains": [],
        "strengths": [],
        "support_areas": [],
        "speech_recorded": False,
        "gaze_recorded": False,
    }
    if assessment is None:
        return summary
    games = list(db.scalars(select(GameSession).where(GameSession.assessment_session_id == assessment.id)))
    trials = list(db.scalars(select(Trial).where(Trial.game_session_id.in_([g.id for g in games])))) if games else []
    scored = [t for t in trials if t.correctness is not None]
    summary["scored_trials"] = len(scored)
    # Unscored = no response, or speech recognition failed: never counted as wrong.
    summary["unscored_trials"] = len(trials) - len(scored)
    summary["games_played"] = sorted({g.game_id for g in games})
    by_domain: dict[str, list[bool]] = {}
    for trial in scored:
        if trial.domain:
            by_domain.setdefault(trial.domain, []).append(bool(trial.correctness))
    summary["domains"] = [
        {"domain": domain, "scored_trials": len(values), "accuracy": round(sum(values) / len(values), 3) if len(values) >= MIN_TRIALS_PER_DOMAIN_SUMMARY else None}
        for domain, values in sorted(by_domain.items())
    ]
    summary["speech_recorded"] = db.scalar(select(SpeechSession.id).where(SpeechSession.assessment_id == assessment.id).limit(1)) is not None
    profile = extract_profile(db, assessment.id)
    if profile:
        summary["gaze_recorded"] = bool(profile[0].get("gaze_available", {}).get("available"))
    # Relative strengths/practice areas come from the existing, non-clinical personalization engine.
    for skill in build_child_profile(db, str(child.id))["skills"]:
        if skill.get("category") == "relative_strength":
            summary["strengths"].append(skill["domain"])
        elif skill.get("category") in {"practice_opportunity", "developing"}:
            summary["support_areas"].append(skill["domain"])
    return summary


def _model_info(model: RegisteredModel) -> dict[str, Any]:
    return {
        "model_id": model.model_id,
        "model_version": model.version,
        "model_name": model.card.get("name", model.model_id),
        "output_type": model.card.get("output_type"),
        "feature_schema_version": model.card.get("feature_schema_version"),
    }


def _band(score: float, thresholds: list[dict[str, Any]]) -> str | None:
    """Only specialist-approved thresholds produce a band; none are invented here."""
    band = None
    for threshold in sorted(thresholds, key=lambda item: float(item["min"])):
        if score >= float(threshold["min"]):
            band = str(threshold["key"])
    return band


def _age(child: ChildProfile, when: datetime | None) -> int | None:
    if child.birth_year is None:
        return None
    return (when or utcnow()).year - child.birth_year


def screen_child(db: Session, child: ChildProfile) -> dict[str, Any]:
    assessment, any_started = _latest_completed(db, child)
    observations = _observations(db, child, assessment)
    model, considered = active_model()
    base: dict[str, Any] = {
        "child_id": str(child.id),
        "assessment_id": str(assessment.id) if assessment else None,
        "assessment_completed_at": assessment.completed_at.isoformat() if assessment and assessment.completed_at else None,
        "target_definition": TARGET_DEFINITION,
        "feature_schema_version": SCREENING_SCHEMA_VERSION,
        "observations": observations,
        "model": _model_info(model) if model else None,
        "models_considered": len(considered),
        "result": None,
        "reasons": [],
    }

    def outcome(status: str, reasons: list[str]) -> dict[str, Any]:
        logger.info("screening status=%s assessment=%s model=%s", status, base["assessment_id"], model.model_id if model else None)
        return {**base, "status": status, "reasons": reasons}

    if assessment is None:
        return outcome("assessment_incomplete" if any_started else "no_assessment", ["no completed assessment"])
    if model is None:
        reasons = sorted({reason for entry in considered for reason in entry.reasons}) or ["no screening model is installed"]
        return outcome("no_eligible_model", reasons)

    validation = model.card.get("validation") or {}
    population = validation.get("intended_population") or {}
    age = _age(child, assessment.completed_at)
    if age is None or not (population["age_min"] <= age <= population["age_max"]):
        return outcome("unsupported_population", ["child age is unknown or outside the model's validated age range"])
    if assessment.language not in population["languages"]:
        return outcome("unsupported_population", [f"model is not validated for language {assessment.language!r}"])
    if observations["scored_trials"] < int(validation.get("min_scored_trials", 15)):
        return outcome("insufficient_observations", [f"at least {validation.get('min_scored_trials', 15)} scored trials are required"])

    existing = db.scalar(
        select(ScreeningResult).where(
            ScreeningResult.assessment_id == assessment.id,
            ScreeningResult.model_id == model.model_id,
            ScreeningResult.model_version == model.version,
        )
    )
    if existing is None:
        profile = extract_profile(db, assessment.id)
        features = validate_features(profile[0] if profile else {})
        if not features.ok:
            return outcome("invalid_features", [f"missing or invalid: {', '.join(features.missing_required + features.invalid)}"])
        score = model.model.score([features.vector])[0]  # type: ignore[union-attr]
        existing = ScreeningResult(
            child_id=child.id,
            assessment_id=assessment.id,
            model_id=model.model_id,
            model_version=model.version,
            feature_schema_version=SCREENING_SCHEMA_VERSION,
            output_type=str(model.card.get("output_type")),
            score=score,
        )
        db.add(existing)
        try:
            db.commit()
        except IntegrityError:  # concurrent request stored the same prediction
            db.rollback()
            existing = db.scalar(select(ScreeningResult).where(ScreeningResult.assessment_id == assessment.id, ScreeningResult.model_id == model.model_id, ScreeningResult.model_version == model.version))
            if existing is None:
                raise
    result = {
        "score": existing.score,
        "score_percent": round(existing.score * 100),
        "output_type": existing.output_type,
        "band": _band(existing.score, validation.get("approved_thresholds") or []),
        "created_at": existing.created_at.isoformat(),
    }
    logger.info("screening status=available assessment=%s model=%s@%s", base["assessment_id"], model.model_id, model.version)
    return {**base, "status": "available", "result": result}
