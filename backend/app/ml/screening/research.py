"""Synthetic research predictor: inference on a child's real game-derived features.

The model was trained on synthetic data only (see ``research_data``). Its output is
the probability of the *synthetic* target under that model, never a real-child
dyslexia probability, and is stored in ``research_predictions`` — never in the
clinical ``screening_results`` table. The parent screening card never reads it.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ml.service import extract_profile
from app.models import AssessmentSession, ChildProfile, ResearchPrediction

from .registry import RegisteredModel, active_research_model
from .schema import SCREENING_FEATURES, SCREENING_SCHEMA_VERSION, validate_features
from .service import _age, _observations

logger = logging.getLogger("dyscover.screening.research")

RESEARCH_LABEL = "Synthetic research score — probability of the synthetic target under this model, NOT a real-child dyslexia probability"
RESEARCH_NOTICE = (
    "This model was trained only on simulated data whose labels are simulator settings chosen by developers. "
    "Its score says how closely this child's activity pattern resembles the simulated 'difficulty' profiles. "
    "It cannot confirm or rule out dyslexia and must not be used to make decisions about a child."
)
_FEATURES = {feature.name: feature for feature in SCREENING_FEATURES}


def model_summary(model: RegisteredModel) -> dict[str, Any]:
    card = model.card
    test = (card.get("evaluation") or {}).get("test") or {}
    return {
        "model_id": model.model_id,
        "model_version": model.version,
        "model_name": card.get("name"),
        "algorithm": card.get("algorithm"),
        "designation": card.get("designation"),
        "training_data": card.get("training_data"),
        "output_type": card.get("output_type"),
        "target_id": card.get("target_id"),
        "target_definition": card.get("target_definition"),
        "feature_schema_version": card.get("feature_schema_version"),
        "artifact_sha256": card.get("artifact_sha256"),
        "created_at": card.get("created_at"),
        "synthetic_test_metrics": {key: test.get("estimate", {}).get(key) for key in ("roc_auc", "pr_auc", "brier", "sensitivity", "specificity")},
        "synthetic_test_counts": test.get("counts"),
        "inputs": card.get("research_inputs"),
    }


def research_overview(db: Session, child: ChildProfile) -> dict[str, Any]:
    model, considered = active_research_model()
    assessments = list(db.scalars(select(AssessmentSession).where(AssessmentSession.child_id == child.id).order_by(AssessmentSession.created_at.desc())))
    stored = {
        row.assessment_id: row
        for row in db.scalars(select(ResearchPrediction).where(ResearchPrediction.child_id == child.id))
        if model is not None and row.model_id == model.model_id and row.model_version == model.version
    }
    return {
        "label": RESEARCH_LABEL,
        "notice": RESEARCH_NOTICE,
        "child_id": str(child.id),
        "model": model_summary(model) if model else None,
        "model_problems": sorted({reason for entry in considered for reason in entry.reasons}) if model is None else [],
        "assessments": [
            {
                "assessment_id": str(item.id),
                "status": item.status,
                "language": item.language,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "completed_at": item.completed_at.isoformat() if item.completed_at else None,
                "has_prediction": item.id in stored,
            }
            for item in assessments
        ],
    }


def _explain(model: RegisteredModel, vector: dict[str, float | None], score: float) -> list[dict[str, Any]]:
    """Per-feature occlusion: how the model's own score changes if this one value were the
    synthetic training median. Computed by the model, not invented; shown with the value's
    position relative to the synthetic training range."""
    reference = model.card.get("feature_reference") or {}
    explanations = []
    for name, value in vector.items():
        ref = reference.get(name) or {}
        item: dict[str, Any] = {
            "name": name,
            "modality": _FEATURES[name].modality,
            "value": value,
            "available": value is not None,
            "training_median": ref.get("median"),
            "outside_training_range": None,
            "score_change_if_typical": None,
        }
        if value is not None and ref.get("median") is not None:
            item["outside_training_range"] = bool(value < ref["p01"] or value > ref["p99"])
            typical = {**vector, name: ref["median"]}
            item["score_change_if_typical"] = round(model.model.score([typical])[0] - score, 4)  # type: ignore[union-attr]
        explanations.append(item)
    explanations.sort(key=lambda item: -abs(item["score_change_if_typical"] or 0))
    return explanations


def predict_assessment(db: Session, child: ChildProfile, assessment: AssessmentSession) -> dict[str, Any]:
    model, considered = active_research_model()
    observations = _observations(db, child, assessment)
    base: dict[str, Any] = {
        "label": RESEARCH_LABEL,
        "notice": RESEARCH_NOTICE,
        "child_id": str(child.id),
        "assessment_id": str(assessment.id),
        "feature_schema_version": SCREENING_SCHEMA_VERSION,
        "model": model_summary(model) if model else None,
        "observations": {key: observations[key] for key in ("scored_trials", "unscored_trials", "games_played", "speech_recorded", "gaze_recorded")},
        "notes": [],
        "features": [],
        "result": None,
    }

    def outcome(status: str, reasons: list[str], **extra: Any) -> dict[str, Any]:
        logger.info("research status=%s assessment=%s model=%s", status, assessment.id, model.model_id if model else None)
        return {**base, **extra, "status": status, "reasons": reasons}

    if model is None:
        return outcome("no_research_model", sorted({r for entry in considered for r in entry.reasons}) or ["no synthetic research model is installed"])
    if assessment.status != "completed":
        return outcome("assessment_incomplete", ["the assessment has not been completed"])
    inputs = model.card["research_inputs"]
    age = _age(child, assessment.completed_at)
    if age is None:
        base["notes"].append("Age is not recorded. The simulator does not model age, so the score is not adjusted for it.")
    elif not inputs["age_min"] <= age <= inputs["age_max"]:
        return outcome("unsupported_population", [f"age {age} is outside {inputs['age_min']}-{inputs['age_max']}"])
    if assessment.language not in inputs["languages"]:
        return outcome("unsupported_population", [f"the synthetic training data covers languages {inputs['languages']}, not {assessment.language!r}"])
    if observations["scored_trials"] < int(inputs["min_scored_trials"]):
        return outcome("insufficient_observations", [f"at least {inputs['min_scored_trials']} scored trials are required (found {observations['scored_trials']}); unscored speech attempts do not count"])
    profile = extract_profile(db, assessment.id)
    features = validate_features(profile[0] if profile else {})
    missing = [name for name in inputs["required_features"] if features.vector.get(name) is None and name not in features.invalid]
    if features.invalid or missing:
        reasons = [f"invalid: {', '.join(features.invalid)}"] if features.invalid else []
        if missing:
            reasons.append(f"missing (not estimated): {', '.join(missing)}")
        return outcome("insufficient_observations" if missing and not features.invalid else "invalid_features", reasons)

    stored = db.scalar(select(ResearchPrediction).where(ResearchPrediction.assessment_id == assessment.id, ResearchPrediction.model_id == model.model_id, ResearchPrediction.model_version == model.version))
    score = model.model.score([features.vector])[0]  # type: ignore[union-attr]
    if stored is None:
        stored = ResearchPrediction(
            child_id=child.id, assessment_id=assessment.id, model_id=model.model_id, model_version=model.version,
            artifact_sha256=str(model.card["artifact_sha256"]), target_id=str(model.card["target_id"]),
            feature_schema_version=SCREENING_SCHEMA_VERSION, output_type=str(model.card["output_type"]), score=score,
        )
        db.add(stored)
        try:
            db.commit()
        except IntegrityError:  # a concurrent request stored the same prediction
            db.rollback()
            stored = db.scalar(select(ResearchPrediction).where(ResearchPrediction.assessment_id == assessment.id, ResearchPrediction.model_id == model.model_id, ResearchPrediction.model_version == model.version))
            if stored is None:
                raise
    elif stored.artifact_sha256 != model.card["artifact_sha256"]:
        # Same id/version but different bytes: refuse rather than mix two models' meanings.
        return outcome("model_version_conflict", ["a different artifact was already recorded under this model id and version"])
    explanation = _explain(model, features.vector, stored.score)
    if any(item["outside_training_range"] for item in explanation):
        base["notes"].append("Some values are outside the range seen in the synthetic training data; the model is extrapolating for those.")
    result = {
        "score": stored.score,
        "score_percent": round(stored.score * 100),
        "output_type": stored.output_type,
        "created_at": stored.created_at.isoformat(),
    }
    return outcome("available", [], features=explanation, result=result)
