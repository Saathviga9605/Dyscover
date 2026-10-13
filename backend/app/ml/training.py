import csv
import hashlib
import json
import pickle
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Any

from .datasets import subject_level_split
from .evaluation import classification_metrics
from .feature_registry import REGISTRY_BY_NAME
from .models import BaselineModel, GradientBoostingBaseline, LogisticBaseline, RandomForestBaseline


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_name: str
    dataset_version: str
    feature_schema_version: str = "1.0"
    algorithm: str = "logistic_regression"
    random_seed: int = 42
    folds: int = 5


def build_rows(session_features: list[tuple[str, str, dict[str, dict[str, Any]], Any | None]]) -> list[dict[str, Any]]:
    return [
        {
            "subject_id": subject_id,
            "session_id": session_id,
            "features": {name: item["value"] if item["available"] and isinstance(item["value"], (int, float)) else None for name, item in features.items()},
            "feature_metadata": {name: {"modality": item.get("modality", "behavior"), "available": bool(item.get("available"))} for name, item in features.items()},
            "target": target,
        }
        for subject_id, session_id, features, target in session_features
    ]


def dataset_manifest(rows: list[dict[str, Any]], dataset_version: str, feature_schema_version: str, split_strategy: str) -> dict[str, Any]:
    subjects = {row["subject_id"] for row in rows}
    modalities = sorted({feature.get("modality", "behavior") for row in rows for feature in row.get("feature_metadata", {}).values()})
    manifest = {"dataset_version": dataset_version, "feature_schema_version": feature_schema_version, "created_at": datetime.now(timezone.utc).isoformat(), "subjects": len(subjects), "sessions": len(rows), "samples": len(rows), "modalities": modalities or ["behavior"], "split_strategy": split_strategy, "label_available": any(row.get("target") is not None for row in rows), "filtering": "semantic validation required; invalid records excluded by caller"}
    manifest["artifact_hash"] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    return manifest


def export_rows(rows: list[dict[str, Any]], destination: Path, manifest: dict[str, Any]) -> Path:
    if destination.exists():
        raise FileExistsError(f"dataset artifact already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {"metadata": manifest, "rows": rows}
    if destination.suffix == ".json":
        destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    elif destination.suffix == ".csv":
        names = sorted({name for row in rows for name in row.get("features", {})})
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["subject_id", "session_id", "target", *names])
            writer.writeheader()
            for row in rows:
                writer.writerow({"subject_id": row["subject_id"], "session_id": row["session_id"], "target": row.get("target"), **row.get("features", {})})
        destination.with_suffix(destination.suffix + ".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    else:
        raise ValueError("only JSON and CSV dataset artifacts are supported")
    return destination


def _model(algorithm: str, feature_names: list[str]) -> BaselineModel:
    choices = {"logistic_regression": LogisticBaseline, "random_forest": RandomForestBaseline, "gradient_boosting": GradientBoostingBaseline}
    if algorithm not in choices:
        raise ValueError(f"unsupported algorithm: {algorithm}")
    return choices[algorithm](feature_names)


def train_research_model(rows: list[dict[str, Any]], labels: list[int], config: ExperimentConfig, output: Path) -> dict[str, Any]:
    if not rows or not labels or len(rows) != len(labels):
        raise ValueError("a labeled dataset is required")
    if any(not row.get("subject_id") for row in rows):
        raise ValueError("subject IDs are required for subject-safe training")
    if len(set(labels)) < 2:
        raise ValueError("at least two validated target classes are required")
    feature_names = sorted({name for row in rows for name in row.get("features", {})})
    unknown_features = sorted(set(feature_names) - set(REGISTRY_BY_NAME))
    if unknown_features:
        raise ValueError(f"features are not in the canonical registry: {', '.join(unknown_features)}")
    for row, label in zip(rows, labels):
        if row.get("target") is not None and row["target"] != label:
            raise ValueError("labels must match row targets")
        row["target"] = label
    split = subject_level_split(rows, seed=config.random_seed)
    train_subjects = {row["subject_id"] for row in split["train"]}
    train_rows = split["train"]
    train_labels = [label for row, label in zip(rows, labels) if row["subject_id"] in train_subjects]
    if len(set(train_labels)) < 2:
        raise ValueError("subject-level training split must contain at least two validated target classes")
    model = _model(config.algorithm, feature_names)
    model.fit(train_rows, train_labels)
    output.parent.mkdir(parents=True, exist_ok=True)
    model_path = output.with_suffix(".pkl")
    with model_path.open("wb") as handle:
        pickle.dump(model, handle)
    evaluation: dict[str, Any] = {}
    for partition in ("validation", "test"):
        partition_rows = split[partition]
        if partition_rows:
            subjects = {row["subject_id"] for row in partition_rows}
            partition_labels = [label for row, label in zip(rows, labels) if row["subject_id"] in subjects]
            if len(set(partition_labels)) > 1:
                evaluation[partition] = classification_metrics(partition_labels, model.predict(partition_rows))
    metadata = {
        "model_id": f"{config.experiment_name}-v1",
        "model_version": "1.0",
        "algorithm": config.algorithm,
        "feature_schema_version": config.feature_schema_version,
        "training_dataset_version": config.dataset_version,
        "training_status": "trained",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "random_seed": config.random_seed,
        "split_strategy": split["strategy"],
        "feature_names": feature_names,
        "artifact": model_path.name,
        "artifact_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "evaluation": evaluation,
        "config": asdict(config),
    }
    output.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def load_research_model(metadata_path: Path, expected_feature_schema_version: str = "1.0") -> tuple[BaselineModel, dict[str, Any]]:
    if not metadata_path.is_file():
        raise FileNotFoundError(f"model metadata does not exist: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("feature_schema_version") != expected_feature_schema_version:
        raise ValueError("model feature schema version is incompatible")
    artifact = metadata_path.parent / metadata.get("artifact", "")
    if not artifact.is_file():
        raise FileNotFoundError(f"model artifact does not exist: {artifact}")
    if hashlib.sha256(artifact.read_bytes()).hexdigest() != metadata.get("artifact_sha256"):
        raise ValueError("model artifact integrity check failed")
    with artifact.open("rb") as handle:
        model = pickle.load(handle)
    if not isinstance(model, BaselineModel) or model.pipeline is None:
        raise ValueError("model artifact is not a trained Dyscover baseline")
    if not set(metadata.get("feature_names", [])) <= set(REGISTRY_BY_NAME):
        raise ValueError("model artifact contains features outside the canonical registry")
    if sorted(model.feature_names) != sorted(metadata.get("feature_names", [])):
        raise ValueError("model metadata does not match the artifact feature schema")
    return model, metadata


def infer_research_model(model: BaselineModel, rows: list[dict[str, Any]], feature_schema_version: str = "1.0") -> dict[str, Any]:
    if feature_schema_version != "1.0":
        raise ValueError("inference feature schema version is incompatible")
    expected = set(model.feature_names)
    for row in rows:
        provided = set(row.get("features", {}))
        if not expected <= provided:
            raise ValueError("inference row is missing required model features")
        if provided - set(REGISTRY_BY_NAME):
            raise ValueError("inference row contains features outside the canonical registry")
    return {"predictions": model.predict(rows), "model_type": model.model_type, "feature_schema_version": feature_schema_version}
