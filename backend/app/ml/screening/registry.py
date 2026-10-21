"""Production screening-model registry and eligibility gate.

A model is *eligible to show parents a percentage* only if every check below
passes. No setting can bypass them: provenance is read from the artifact itself,
and the validation evidence must be recorded in the model card by reviewers.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import get_settings

from .model import ScreeningModel
from .research_data import RESEARCH_TARGET_ID
from .schema import SCREENING_SCHEMA_VERSION, TARGET_ID

logger = logging.getLogger("dyscover.screening")


@dataclass
class RegisteredModel:
    card: dict[str, Any]
    model: ScreeningModel | None
    eligible: bool
    reasons: list[str] = field(default_factory=list)

    @property
    def model_id(self) -> str:
        return str(self.card.get("model_id", "unknown"))

    @property
    def version(self) -> str:
        return str(self.card.get("version", "unknown"))


def _load_artifact(card_path: Path, card: dict[str, Any]) -> tuple[ScreeningModel | None, list[str]]:
    name = card.get("artifact") or ""
    if not name or Path(name).name != name:
        return None, ["artifact name must be a plain file name"]
    artifact = card_path.parent / name
    if not artifact.is_file():
        return None, ["artifact file is missing"]
    data = artifact.read_bytes()
    if hashlib.sha256(data).hexdigest() != card.get("artifact_sha256"):
        return None, ["artifact SHA-256 does not match the model card"]
    try:
        model = pickle.loads(data)  # noqa: S301 - operator-installed, hash-verified artifact
    except Exception:  # corrupted or incompatible artifact
        logger.exception("Screening artifact could not be loaded")
        return None, ["artifact could not be loaded"]
    if not isinstance(model, ScreeningModel):
        return None, ["artifact is not a ScreeningModel"]
    runtime = card.get("runtime") or {}
    if runtime.get("scikit_learn") and _minor(runtime["scikit_learn"]) != _minor(_sklearn_version()):
        return None, [f"artifact was built with scikit-learn {runtime['scikit_learn']}, runtime has {_sklearn_version()}"]
    return model, []


def _sklearn_version() -> str:
    import sklearn

    return str(sklearn.__version__)


def _minor(version: str) -> str:
    return ".".join(version.split(".")[:2])


def evaluate_eligibility(card: dict[str, Any], model: ScreeningModel | None) -> list[str]:
    """Return the reasons a model may NOT be used for real children (empty = eligible)."""
    reasons: list[str] = []
    validation = card.get("validation") or {}
    if card.get("target_id") != TARGET_ID:
        reasons.append("model targets a different outcome")
    if card.get("feature_schema_version") != SCREENING_SCHEMA_VERSION:
        reasons.append("feature schema version is incompatible")
    if card.get("designation") == "synthetic_research":
        reasons.append("model is designated for synthetic research only")
    if card.get("training_data") != "real":
        reasons.append("model was not trained on real labelled data")
    if card.get("output_type") != "calibrated_probability":
        reasons.append("model output is not a calibrated probability")
    if model is not None:
        if model.training_data != "real":
            reasons.append("artifact provenance is synthetic")
        if model.target_id != TARGET_ID:
            reasons.append("artifact targets a different outcome")
        if model.output_type != card.get("output_type") or model.feature_schema_version != card.get("feature_schema_version"):
            reasons.append("artifact provenance does not match the model card")
    evaluation = card.get("evaluation") or {}
    if not evaluation.get("reliable_sample_size"):
        reasons.append("held-out evaluation sample is too small to be reliable")
    for key, message in (
        ("external_validation_reference", "no external validation study is recorded"),
        ("specialist_review_reference", "no qualified specialist review is recorded"),
        ("ethics_approval_reference", "no ethics approval is recorded"),
    ):
        if not validation.get(key):
            reasons.append(message)
    population = validation.get("intended_population") or {}
    if not population.get("languages") or population.get("age_min") is None or population.get("age_max") is None:
        reasons.append("intended population (ages, languages) is not defined")
    return reasons


def load_registry(directory: Path | None = None) -> list[RegisteredModel]:
    root = directory or Path(get_settings().screening_model_dir)
    if not root.is_dir():
        return []
    registered: list[RegisteredModel] = []
    for card_path in sorted(root.glob("*/model_card.json")):
        try:
            card = json.loads(card_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            registered.append(RegisteredModel({"model_id": card_path.parent.name}, None, False, ["model card is unreadable"]))
            continue
        model, artifact_problems = _load_artifact(card_path, card)
        reasons = artifact_problems + evaluate_eligibility(card, model)
        registered.append(RegisteredModel(card, model, not reasons and model is not None, reasons))
    return registered


def active_model(directory: Path | None = None) -> tuple[RegisteredModel | None, list[RegisteredModel]]:
    """The newest eligible model (by created_at), plus everything that was considered."""
    registry = load_registry(directory)
    eligible = sorted((m for m in registry if m.eligible), key=lambda m: str(m.card.get("created_at", "")), reverse=True)
    return (eligible[0] if eligible else None), registry


# --- synthetic research models ------------------------------------------------------

def research_eligibility(card: dict[str, Any], model: ScreeningModel | None) -> list[str]:
    """Reasons a model may NOT be served by the research route (empty = usable there).

    The research route only ever serves synthetic models, so a real or unlabelled
    model placed in the research directory is refused rather than run unreviewed.
    """
    reasons: list[str] = []
    if card.get("designation") != "synthetic_research" or card.get("training_data") != "synthetic":
        reasons.append("model card is not a synthetic research model")
    if card.get("target_id") != RESEARCH_TARGET_ID:
        reasons.append("model targets a different outcome")
    if card.get("feature_schema_version") != SCREENING_SCHEMA_VERSION:
        reasons.append("feature schema version is incompatible")
    if not card.get("research_inputs"):
        reasons.append("research input requirements are not defined")
    if model is not None and (model.training_data != "synthetic" or model.target_id != RESEARCH_TARGET_ID or model.output_type != card.get("output_type") or model.feature_schema_version != card.get("feature_schema_version")):
        reasons.append("artifact provenance does not match the model card")
    return reasons


def load_research_registry(directory: Path | None = None) -> list[RegisteredModel]:
    root = directory or Path(get_settings().research_demo_model_dir)
    if not root.is_dir():
        return []
    registered: list[RegisteredModel] = []
    for card_path in sorted(root.glob("*/model_card.json")):
        try:
            card = json.loads(card_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            registered.append(RegisteredModel({"model_id": card_path.parent.name}, None, False, ["model card is unreadable"]))
            continue
        model, artifact_problems = _load_artifact(card_path, card)
        reasons = artifact_problems + research_eligibility(card, model)
        registered.append(RegisteredModel(card, model, not reasons and model is not None, reasons))
    return registered


def active_research_model(directory: Path | None = None) -> tuple[RegisteredModel | None, list[RegisteredModel]]:
    registry = load_research_registry(directory)
    usable = sorted((m for m in registry if m.eligible), key=lambda m: str(m.card.get("created_at", "")), reverse=True)
    return (usable[0] if usable else None), registry
