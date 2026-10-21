"""The trained screening model object stored in an artifact.

Provenance (``training_data``, ``output_type``) is baked into the artifact at
training time and cross-checked against the model card, so editing a JSON card
or an environment variable cannot turn a synthetic model into a real one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

TrainingData = Literal["synthetic", "real"]
OutputType = Literal["calibrated_probability", "research_score"]


@dataclass
class ScreeningModel:
    pipeline: Any
    feature_names: tuple[str, ...]
    feature_schema_version: str
    target_id: str
    training_data: TrainingData
    output_type: OutputType
    algorithm: str
    hyperparameters: dict[str, Any] = field(default_factory=dict)

    def matrix(self, vectors: list[dict[str, float | None]]) -> np.ndarray:
        return np.array(
            [[np.nan if vector.get(name) is None else float(vector[name]) for name in self.feature_names] for vector in vectors],
            dtype=float,
        )

    def score(self, vectors: list[dict[str, float | None]]) -> list[float]:
        """Positive-class output in [0, 1]. Whether it is a probability depends on ``output_type``."""
        return [float(value) for value in self.pipeline.predict_proba(self.matrix(vectors))[:, 1]]
