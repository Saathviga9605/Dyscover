import json
import pickle
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .datasets import grouped_folds, subject_level_split
from .models import BaselineModel, GradientBoostingBaseline, LogisticBaseline, RandomForestBaseline


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_name: str
    dataset_version: str
    feature_schema_version: str = "1.0"
    algorithm: str = "logistic_regression"
    random_seed: int = 42
    folds: int = 5


def _model(algorithm: str, feature_names: list[str]) -> BaselineModel:
    choices = {"logistic_regression": LogisticBaseline, "random_forest": RandomForestBaseline, "gradient_boosting": GradientBoostingBaseline}
    if algorithm not in choices: raise ValueError(f"unsupported algorithm: {algorithm}")
    return choices[algorithm](feature_names)


def train_research_model(rows: list[dict[str, Any]], labels: list[int], config: ExperimentConfig, output: Path) -> dict[str, Any]:
    if not rows or not labels or len(rows) != len(labels): raise ValueError("a labeled dataset is required")
    if any(not row.get("subject_id") for row in rows): raise ValueError("subject IDs are required for subject-safe training")
    if len(set(labels)) < 2: raise ValueError("at least two validated target classes are required")
    feature_names = sorted({name for row in rows for name in row.get("features", {})})
    split = subject_level_split(rows, seed=config.random_seed)
    model = _model(config.algorithm, feature_names)
    model.fit(rows, labels)
    output.parent.mkdir(parents=True, exist_ok=True)
    model_path = output.with_suffix(".pkl")
    with model_path.open("wb") as handle: pickle.dump(model, handle)
    metadata = {"model_id": f"{config.experiment_name}-v1", "model_version": "1.0", "algorithm": config.algorithm, "feature_schema_version": config.feature_schema_version, "training_dataset_version": config.dataset_version, "training_status": "trained", "created_at": datetime.now(timezone.utc).isoformat(), "random_seed": config.random_seed, "split_strategy": split["strategy"], "feature_names": feature_names, "artifact": str(model_path)}
    output.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata
