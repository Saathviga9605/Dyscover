import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Any


def build_rows(session_features: list[tuple[str, str, dict[str, dict[str, Any]], Any | None]]) -> list[dict[str, Any]]:
    rows = []
    for subject_id, session_id, features, target in session_features:
        rows.append({"subject_id": subject_id, "session_id": session_id, "features": {name: item["value"] if item["available"] and isinstance(item["value"], (int, float)) else None for name, item in features.items()}, "target": target})
    return rows


def subject_level_split(rows: list[dict[str, Any]], seed: int = 42, train_ratio: float = .7, validation_ratio: float = .15) -> dict[str, Any]:
    if not 0 < train_ratio < 1 or not 0 <= validation_ratio < 1 or train_ratio + validation_ratio >= 1:
        raise ValueError("split ratios must leave a non-empty test partition")
    subjects = sorted({row["subject_id"] for row in rows})
    Random(seed).shuffle(subjects)
    train_end = max(1, round(len(subjects) * train_ratio)) if subjects else 0
    validation_end = min(len(subjects), train_end + max(1, round(len(subjects) * validation_ratio))) if len(subjects) > 1 else train_end
    groups = {"train": set(subjects[:train_end]), "validation": set(subjects[train_end:validation_end]), "test": set(subjects[validation_end:])}
    return {"train": [row for row in rows if row["subject_id"] in groups["train"]], "validation": [row for row in rows if row["subject_id"] in groups["validation"]], "test": [row for row in rows if row["subject_id"] in groups["test"]], "strategy": "subject_level_random_split", "random_seed": seed}


def grouped_folds(rows: list[dict[str, Any]], folds: int = 5, seed: int = 42) -> list[dict[str, list[dict[str, Any]]]]:
    subjects = sorted({row["subject_id"] for row in rows})
    if folds < 2 or len(subjects) < folds: raise ValueError("grouped folds require at least as many subjects as folds")
    Random(seed).shuffle(subjects)
    partitions = [set() for _ in range(folds)]
    for index, subject in enumerate(subjects): partitions[index % folds].add(subject)
    return [{"train": [row for row in rows if row["subject_id"] not in partitions[index]], "validation": [row for row in rows if row["subject_id"] in partitions[index]]} for index in range(folds)]


def dataset_manifest(rows: list[dict[str, Any]], dataset_version: str, feature_schema_version: str, split_strategy: str) -> dict[str, Any]:
    subjects = {row["subject_id"] for row in rows}
    modalities = sorted({feature.get("modality", "behavior") for row in rows for feature in row.get("feature_metadata", {}).values()})
    manifest = {"dataset_version": dataset_version, "feature_schema_version": feature_schema_version, "created_at": datetime.now(timezone.utc).isoformat(), "subjects": len(subjects), "sessions": len(rows), "samples": len(rows), "modalities": modalities or ["behavior"], "split_strategy": split_strategy, "label_available": any(row.get("target") is not None for row in rows), "filtering": "semantic validation required; invalid records excluded by caller"}
    manifest["artifact_hash"] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    return manifest


def export_rows(rows: list[dict[str, Any]], destination: Path, manifest: dict[str, Any]) -> Path:
    if destination.exists(): raise FileExistsError(f"dataset artifact already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {"metadata": manifest, "rows": rows}
    if destination.suffix == ".json": destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    elif destination.suffix == ".csv":
        names = sorted({name for row in rows for name in row.get("features", {})})
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["subject_id", "session_id", "target", *names])
            writer.writeheader()
            for row in rows: writer.writerow({"subject_id": row["subject_id"], "session_id": row["session_id"], "target": row.get("target"), **row.get("features", {})})
        destination.with_suffix(destination.suffix + ".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    else: raise ValueError("only JSON and CSV dataset artifacts are supported")
    return destination
