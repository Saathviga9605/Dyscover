import json
from pathlib import Path

import pytest

from app.ml.datasets import dataset_manifest, export_rows, grouped_folds, subject_level_split
from app.ml.evaluation import classification_metrics
from app.ml.feature_registry import REGISTRY_BY_NAME
from app.ml.registry import list_models


def test_feature_registry_contains_extractor_features() -> None:
    required = {"overall_accuracy", "mean_reaction_time_ms", "total_error_count", "completion_rate"}
    assert required.issubset(REGISTRY_BY_NAME)
    assert all(item.unit and item.modality for item in REGISTRY_BY_NAME.values())


def test_grouped_folds_keep_subjects_separate() -> None:
    rows = [{"subject_id": subject, "session_id": f"{subject}-{index}", "features": {"accuracy": .5}} for subject in "abcde" for index in range(2)]
    folds = grouped_folds(rows, folds=5, seed=42)
    for fold in folds:
        train_subjects = {row["subject_id"] for row in fold["train"]}
        validation_subjects = {row["subject_id"] for row in fold["validation"]}
        assert train_subjects.isdisjoint(validation_subjects)


def test_dataset_export_is_immutable_and_has_manifest(tmp_path: Path) -> None:
    rows = [{"subject_id": "subject-a", "session_id": "session-a", "features": {"overall_accuracy": .75}, "target": None}]
    manifest = dataset_manifest(rows, "v1", "1.0", "subject_level_random_split")
    output = export_rows(rows, tmp_path / "dataset.json", manifest)
    assert json.loads(output.read_text())["metadata"]["artifact_hash"]
    with pytest.raises(FileExistsError):
        export_rows(rows, output, manifest)


def test_classification_metrics_do_not_invent_missing_classes() -> None:
    result = classification_metrics([1, 1], [1, 1])
    assert result["accuracy"] == 1
    assert result["precision"] is None


def test_registry_models_are_not_claimed_validated() -> None:
    assert list_models()
    assert all(model.status == "unavailable" for model in list_models())
