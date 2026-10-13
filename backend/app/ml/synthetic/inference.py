"""Isolated research inference helper for synthetic interaction profiles.

All outputs carry prominent SYNTHETIC_RESEARCH_ONLY disclaimers.
Synthetic inference is strictly prohibited from writing to child records, parent dashboards,
or educator summaries.
"""

from __future__ import annotations

from typing import Any

from app.ml.feature_registry import REGISTRY_BY_NAME
from app.ml.models import BaselineModel
from .generator import SYNTHETIC_SCHEMA_VERSION

DISCLAIMER_TEXT = (
    "RESEARCH USE ONLY: This output represents a simulated interaction profile classification. "
    "It is NOT a dyslexia assessment, diagnostic conclusion, or clinical risk indicator. "
    "Do not record this output in child profiles, parent reports, or educational records."
)


def infer_synthetic_profile(
    model: BaselineModel,
    rows: list[dict[str, Any]],
    feature_schema_version: str = SYNTHETIC_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Execute synthetic profile classification with explicit non-clinical tagging."""
    if feature_schema_version != SYNTHETIC_SCHEMA_VERSION:
        raise ValueError(
            f"Schema version mismatch: expected {SYNTHETIC_SCHEMA_VERSION}, got {feature_schema_version}"
        )

    expected_features = set(model.feature_names)
    for idx, row in enumerate(rows):
        features = row.get("features", {})
        if not isinstance(features, dict):
            raise ValueError(f"Row {idx} contains malformed features structure")

        provided_features = set(features.keys())
        missing = expected_features - provided_features
        if missing:
            raise ValueError(f"Row {idx} is missing required features: {sorted(missing)}")

        unknown = provided_features - set(REGISTRY_BY_NAME)
        if unknown:
            raise ValueError(f"Row {idx} contains unknown features: {sorted(unknown)}")

    predictions = model.predict(rows)
    proba: list[list[float]] | None = None
    try:
        proba = model.predict_proba(rows)
    except Exception:
        proba = None

    return {
        "status": "SYNTHETIC_RESEARCH_ONLY",
        "scientific_disclaimer": DISCLAIMER_TEXT,
        "clinical_use": "prohibited",
        "intended_use": "simulator_profile_classification",
        "model_type": model.model_type,
        "feature_schema_version": feature_schema_version,
        "sample_count": len(rows),
        "predictions": predictions,
        "probabilities": proba,
    }

