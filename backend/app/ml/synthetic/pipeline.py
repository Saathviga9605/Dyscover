"""End-to-end training and evaluation pipeline for synthetic interaction profiles.

Strict isolation:
- Models trained here carry synthetic=True and intended_use='simulator_profile_classification'.
- They are prohibited from clinical use or deployment into the production inference registry.
"""

from __future__ import annotations

import hashlib
import json
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.ml.datasets import subject_level_split
from app.ml.evaluation import class_distribution
from app.ml.feature_registry import REGISTRY_BY_NAME
from app.ml.models import (
    BaselineModel,
    DummyBaseline,
    GradientBoostingBaseline,
    LogisticBaseline,
    RandomForestBaseline,
)
from .evaluation import (
    evaluate_partition,
    evaluate_subgroups,
    generate_evaluation_report,
)
from .generator import SYNTHETIC_SCHEMA_VERSION, SIMULATOR_VERSION


def get_synthetic_estimator(algorithm: str, feature_names: list[str]) -> BaselineModel:
    """Instantiate a baseline model matching the requested algorithm."""
    algorithms: dict[str, type[BaselineModel]] = {
        "dummy": DummyBaseline,
        "logistic_regression": LogisticBaseline,
        "random_forest": RandomForestBaseline,
        "gradient_boosting": GradientBoostingBaseline,
    }
    if algorithm not in algorithms:
        raise ValueError(
            f"Unsupported synthetic estimator: '{algorithm}'. Supported: {sorted(algorithms)}"
        )
    return algorithms[algorithm](feature_names)


def train_synthetic_models(
    dataset: dict[str, Any],
    output_dir: Path,
    algorithms: tuple[str, ...] = ("dummy", "logistic_regression", "random_forest", "gradient_boosting"),
) -> dict[str, Any]:
    """Train real classifiers on synthetic interaction profiles with subject-level splitting."""
    rows = [r for r in dataset.get("rows", []) if r.get("eligible")]
    if not rows:
        raise ValueError("Synthetic dataset contains no eligible rows for training")

    feature_names = sorted(REGISTRY_BY_NAME.keys())
    seed = int(dataset.get("metadata", {}).get("seed", 42))
    dataset_checksum = dataset.get("metadata", {}).get("data_checksum", "")

    # Subject-level split prevents data leakage across partitions
    split = subject_level_split(rows, seed=seed)
    train_rows = split["train"]
    val_rows = split["validation"]
    test_rows = split["test"]

    train_labels = [r["target"] for r in train_rows]
    val_labels = [r["target"] for r in val_rows]
    test_labels = [r["target"] for r in test_rows]

    # Verify class coverage in training partition
    train_dist = class_distribution(train_labels)
    if len(train_dist["counts"]) < 2:
        raise ValueError(
            f"Subject-level training partition must contain at least 2 distinct target classes, got {len(train_dist['counts'])}"
        )

    all_classes = sorted(set(r["target"] for r in rows))
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}

    train_subjects = len({r["subject_id"] for r in train_rows})
    val_subjects = len({r["subject_id"] for r in val_rows})
    test_subjects = len({r["subject_id"] for r in test_rows})

    dummy_test_acc: float | None = None

    for algo in algorithms:
        model = get_synthetic_estimator(algo, feature_names)

        # Preprocessing & model fitting (fitted on training rows ONLY)
        model.fit(train_rows, train_labels)

        # Predictions on held-out partitions
        val_preds = model.predict(val_rows) if val_rows else []
        test_preds = model.predict(test_rows) if test_rows else []

        val_metrics = evaluate_partition(val_labels, val_preds, all_classes) if val_rows else {}
        test_metrics = evaluate_partition(test_labels, test_preds, all_classes) if test_rows else {}

        if algo == "dummy":
            dummy_test_acc = test_metrics.get("accuracy")

        subgroup_metrics = evaluate_subgroups(test_rows, test_labels, test_preds) if test_rows else {}

        eval_report = generate_evaluation_report(
            algorithm=algo,
            train_subjects=train_subjects,
            val_subjects=val_subjects,
            test_subjects=test_subjects,
            val_metrics=val_metrics,
            test_metrics=test_metrics,
            subgroup_metrics=subgroup_metrics,
            dummy_test_accuracy=dummy_test_acc,
        )

        # Artifact serialization
        artifact_path = output_dir / f"{algo}.pkl"
        with artifact_path.open("wb") as f:
            pickle.dump(model, f)

        artifact_bytes = artifact_path.read_bytes()
        artifact_sha256 = hashlib.sha256(artifact_bytes).hexdigest()

        metadata = {
            "model_id": f"synthetic-{algo}-v1",
            "model_type": model.model_type,
            "algorithm": algo,
            "synthetic": True,
            "intended_use": "simulator_profile_classification",
            "clinical_use": "prohibited",
            "feature_schema_version": SYNTHETIC_SCHEMA_VERSION,
            "simulator_version": SIMULATOR_VERSION,
            "dataset_checksum": dataset_checksum,
            "feature_names": feature_names,
            "artifact": artifact_path.name,
            "artifact_sha256": artifact_sha256,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "class_distribution": train_dist,
            "evaluation": eval_report,
        }

        meta_path = output_dir / f"{algo}.json"
        meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        results[algo] = metadata

    return results


def load_synthetic_model(
    metadata_path: Path,
    expected_schema_version: str = SYNTHETIC_SCHEMA_VERSION,
) -> tuple[BaselineModel, dict[str, Any]]:
    """Load a synthetic research model and verify artifact integrity and schema compatibility."""
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Synthetic model metadata does not exist: {metadata_path}")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    # Strict synthetic identity checks
    if not metadata.get("synthetic"):
        raise ValueError("Model is not marked as synthetic")
    if metadata.get("clinical_use") != "prohibited":
        raise ValueError("Model does not have prohibited clinical use status")
    if metadata.get("feature_schema_version") != expected_schema_version:
        raise ValueError(
            f"Schema version mismatch: expected {expected_schema_version}, got {metadata.get('feature_schema_version')}"
        )

    feat_names = metadata.get("feature_names", [])
    unknown = set(feat_names) - set(REGISTRY_BY_NAME)
    if unknown:
        raise ValueError(f"Model contains unregistered features: {sorted(unknown)}")

    artifact_name = metadata.get("artifact", "")
    # Artifacts must live next to their metadata; reject path components (e.g. "../x.pkl").
    if not artifact_name or Path(artifact_name).name != artifact_name:
        raise ValueError("Model artifact name must be a plain file name")
    artifact_path = metadata_path.parent / artifact_name
    if not artifact_path.is_file():
        raise FileNotFoundError(f"Model artifact binary not found: {artifact_path}")

    actual_sha = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    if actual_sha != metadata.get("artifact_sha256"):
        raise ValueError("Model artifact integrity check failed: SHA256 mismatch")

    # pickle executes code on load: artifacts are operator-produced files only, verified by
    # SHA-256 above. No API endpoint accepts model uploads.
    with artifact_path.open("rb") as f:
        model = pickle.load(f)  # noqa: S301

    if not isinstance(model, BaselineModel) or model.pipeline is None:
        raise ValueError("Artifact is not a valid trained BaselineModel")

    return model, metadata

