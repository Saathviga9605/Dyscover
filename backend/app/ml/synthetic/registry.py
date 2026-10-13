"""Distinct research artifact registry for synthetic interaction-profile models.

Strict Isolation Boundary:
- Synthetic research models are registered exclusively in this module.
- Synthetic models are strictly prevented from entering the production registry or being used for child/parent/educator screening.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .pipeline import load_synthetic_model


@dataclass(frozen=True)
class SyntheticModelRecord:
    model_id: str
    algorithm: str
    metadata_path: str
    artifact_sha256: str
    dataset_checksum: str
    feature_schema_version: str
    simulator_version: str
    synthetic: bool = True
    intended_use: str = "simulator_profile_classification"
    clinical_use: str = "prohibited"


class ResearchArtifactRegistry:
    """In-memory or filesystem-backed registry dedicated exclusively to synthetic research models."""

    def __init__(self) -> None:
        self._models: dict[str, SyntheticModelRecord] = {}

    def register(self, metadata_path: Path) -> SyntheticModelRecord:
        """Register a trained synthetic model into the research registry."""
        if not metadata_path.is_file():
            raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

        _, metadata = load_synthetic_model(metadata_path)

        record = SyntheticModelRecord(
            model_id=metadata["model_id"],
            algorithm=metadata["algorithm"],
            metadata_path=str(metadata_path.resolve()),
            artifact_sha256=metadata["artifact_sha256"],
            dataset_checksum=metadata["dataset_checksum"],
            feature_schema_version=metadata["feature_schema_version"],
            simulator_version=metadata["simulator_version"],
            synthetic=True,
            intended_use=metadata["intended_use"],
            clinical_use=metadata["clinical_use"],
        )
        self._models[record.model_id] = record
        return record

    def get(self, model_id: str) -> SyntheticModelRecord | None:
        return self._models.get(model_id)

    def list_all(self) -> list[SyntheticModelRecord]:
        return list(self._models.values())

    def clear(self) -> None:
        self._models.clear()


# Default singleton instance for research session scope
RESEARCH_REGISTRY = ResearchArtifactRegistry()

