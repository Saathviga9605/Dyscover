"""Train, evaluate, calibrate and package a screening model.

Usage (real data — requires a provenance file, see docs/readiness/ai-ml-validation.md §8):
    python -m app.ml.screening.training --data dataset.csv --provenance provenance.json --output models/screening/<id>

Synthetic research model (research inference only; never eligible for children's screening):
    python -m app.ml.screening.training --synthetic-demo --output artifacts/screening-synthetic/dyscover-research-synthetic

Method: participant-grouped stratified splits (test, then validation) so one child
never appears in two partitions; preprocessing fitted inside the pipeline on the
training partition only; a univariate leakage check on the training partition;
hyper-parameters chosen on validation ROC-AUC; sigmoid calibration on the
validation partition only when it is large enough; final evaluation on held-out
participants with participant-level bootstrap intervals.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pickle
import platform
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .model import ScreeningModel
from .research_data import RESEARCH_TARGET_DEFINITION, RESEARCH_TARGET_ID, generate_research_dataset
from .schema import FEATURE_NAMES, SCREENING_SCHEMA_VERSION, TARGET_DEFINITION, TARGET_ID, assert_schema_is_leak_free, validate_features

REQUIRED_PROVENANCE = ("source", "license", "consent_and_ethics", "label_definition", "label_method", "population")
# Below these sizes metrics are reported but flagged as not reliable evidence.
MIN_RELIABLE_TEST_PARTICIPANTS = 100
MIN_RELIABLE_TEST_POSITIVES = 30
# Calibration is only fitted when the validation partition can support it.
MIN_CALIBRATION_PARTICIPANTS = 60
MIN_CALIBRATION_PER_CLASS = 15
# A single feature that separates the classes almost perfectly on the training
# partition is treated as label leakage, not as signal.
LEAKAGE_AUC_LIMIT = 0.98
SELECTION_CRITERION = "highest validation ROC-AUC among non-baseline candidates; ties keep the earlier (simpler) candidate"


class LeakageError(ValueError):
    pass


def runtime_info() -> dict[str, str]:
    import sklearn

    return {"python": platform.python_version(), "numpy": np.__version__, "scikit_learn": sklearn.__version__}


@dataclass
class LabelledRow:
    participant_id: str
    label: int
    vector: dict[str, float | None]


def prepare_rows(raw_rows: list[dict[str, Any]]) -> tuple[list[LabelledRow], dict[str, int]]:
    """Validate labels and features; excluded rows are counted, never silently repaired.

    Exact duplicates (same participant, same feature vector) are dropped; participants
    whose rows carry contradictory labels are excluded entirely.
    """
    rows: list[LabelledRow] = []
    excluded = {"invalid_label": 0, "missing_participant": 0, "missing_required_features": 0, "invalid_features": 0, "duplicate": 0, "contradictory_label": 0}
    seen: set[tuple[str, str]] = set()
    for raw in raw_rows:
        if raw.get("label") not in (0, 1, "0", "1"):
            excluded["invalid_label"] += 1
            continue
        if not str(raw.get("participant_id") or "").strip():
            excluded["missing_participant"] += 1
            continue
        validation = validate_features(raw.get("features", {}))
        if validation.missing_required:
            excluded["missing_required_features"] += 1
            continue
        if validation.invalid:
            excluded["invalid_features"] += 1
            continue
        key = (str(raw["participant_id"]), json.dumps(validation.vector, sort_keys=True))
        if key in seen:
            excluded["duplicate"] += 1
            continue
        seen.add(key)
        rows.append(LabelledRow(str(raw["participant_id"]), int(raw["label"]), validation.vector))
    labels: dict[str, set[int]] = {}
    for row in rows:
        labels.setdefault(row.participant_id, set()).add(row.label)
    contradictory = {pid for pid, values in labels.items() if len(values) > 1}
    if contradictory:
        excluded["contradictory_label"] = sum(row.participant_id in contradictory for row in rows)
        rows = [row for row in rows if row.participant_id not in contradictory]
    return rows, excluded


def grouped_split(rows: list[LabelledRow], seed: int) -> dict[str, list[LabelledRow]]:
    """Stratified, participant-grouped split: ~20% test, ~20% validation, rest train."""
    from sklearn.model_selection import StratifiedGroupKFold

    labels = np.array([row.label for row in rows])
    groups = np.array([row.participant_id for row in rows])
    outer = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    rest_index, test_index = next(outer.split(np.zeros(len(rows)), labels, groups))
    inner = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=seed + 1)
    train_sub, val_sub = next(inner.split(np.zeros(len(rest_index)), labels[rest_index], groups[rest_index]))
    pick = lambda indexes: [rows[i] for i in indexes]  # noqa: E731
    split = {"train": pick(rest_index[train_sub]), "validation": pick(rest_index[val_sub]), "test": pick(test_index)}
    participants = [{row.participant_id for row in part} for part in split.values()]
    if participants[0] & participants[1] or participants[0] & participants[2] or participants[1] & participants[2]:
        raise AssertionError("participant leaked across partitions")
    return split


def _candidates(seed: int) -> list[tuple[str, dict[str, Any], Any]]:
    from sklearn.dummy import DummyClassifier
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    def imputer():
        # Missing modalities stay missing: median fill *plus* indicator columns.
        return SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)

    candidates: list[tuple[str, dict[str, Any], Any]] = [
        ("dummy_prior", {}, Pipeline([("impute", imputer()), ("model", DummyClassifier(strategy="prior"))]))
    ]
    for c in (0.1, 1.0, 10.0):
        candidates.append(("logistic_regression", {"C": c}, Pipeline([("impute", imputer()), ("scale", StandardScaler()), ("model", LogisticRegression(C=c, max_iter=2000, class_weight="balanced", random_state=seed))])))
    for depth in (4, 8):
        candidates.append(("random_forest", {"max_depth": depth, "n_estimators": 300}, Pipeline([("impute", imputer()), ("model", RandomForestClassifier(max_depth=depth, n_estimators=300, class_weight="balanced", random_state=seed))])))
    for depth in (2, 3):
        candidates.append(("gradient_boosting", {"max_depth": depth, "n_estimators": 150}, Pipeline([("impute", imputer()), ("model", GradientBoostingClassifier(max_depth=depth, n_estimators=150, random_state=seed))])))
    return candidates


def _matrix(rows: list[LabelledRow]) -> tuple[np.ndarray, np.ndarray]:
    x = np.array([[np.nan if row.vector[name] is None else row.vector[name] for name in FEATURE_NAMES] for row in rows], dtype=float)
    return x, np.array([row.label for row in rows])


def _auc(labels: np.ndarray, scores: np.ndarray) -> float | None:
    from sklearn.metrics import roc_auc_score

    return float(roc_auc_score(labels, scores)) if len(set(labels.tolist())) == 2 else None


def check_leakage(x: np.ndarray, y: np.ndarray, names: tuple[str, ...], limit: float = LEAKAGE_AUC_LIMIT) -> dict[str, float]:
    """Univariate ROC-AUC per feature on the training partition; raises if any feature is near-perfect."""
    assert_schema_is_leak_free(names)
    report: dict[str, float] = {}
    for column, name in enumerate(names):
        present = ~np.isnan(x[:, column])
        if present.sum() < 10 or len(set(y[present].tolist())) < 2 or len(set(x[present, column].tolist())) < 2:
            continue
        auc = _auc(y[present], x[present, column])
        if auc is None:
            continue
        separation = max(auc, 1 - auc)
        report[name] = round(separation, 4)
        if separation >= limit:
            raise LeakageError(f"Feature {name!r} separates the labels with AUC {separation:.3f} on training data; suspected label leakage")
    return report


def threshold_metrics(labels: np.ndarray, scores: np.ndarray, threshold: float) -> dict[str, float | None]:
    predicted = scores >= threshold
    tp = int(np.sum(predicted & (labels == 1)))
    tn = int(np.sum(~predicted & (labels == 0)))
    fp = int(np.sum(predicted & (labels == 0)))
    fn = int(np.sum(~predicted & (labels == 1)))
    ratio = lambda a, b: (a / b) if b else None  # noqa: E731
    return {"sensitivity": ratio(tp, tp + fn), "specificity": ratio(tn, tn + fp), "ppv": ratio(tp, tp + fp), "npv": ratio(tn, tn + fn), "tp": tp, "tn": tn, "fp": fp, "fn": fn}


def _threshold_for_sensitivity(labels: np.ndarray, scores: np.ndarray, target: float) -> float | None:
    positives = np.sort(scores[labels == 1])
    if not len(positives):
        return None
    index = int(np.floor((1 - target) * len(positives)))
    return float(positives[min(index, len(positives) - 1)])


def evaluate(labels: np.ndarray, scores: np.ndarray, participants: list[str], threshold: float | None, seed: int, bootstrap: int = 1000) -> dict[str, Any]:
    """Metrics that cannot be computed (one class present, no positives) are ``None``, never guessed."""
    from sklearn.metrics import average_precision_score, brier_score_loss

    def point(lab: np.ndarray, sc: np.ndarray) -> dict[str, float | None]:
        out: dict[str, float | None] = {
            "roc_auc": _auc(lab, sc),
            "pr_auc": float(average_precision_score(lab, sc)) if lab.sum() else None,
            "brier": float(brier_score_loss(lab, sc)),
        }
        if threshold is not None:
            out.update({k: v for k, v in threshold_metrics(lab, sc, threshold).items() if k in ("sensitivity", "specificity", "ppv", "npv")})
        return out

    estimate = point(labels, scores)
    confusion = {k: v for k, v in threshold_metrics(labels, scores, threshold).items() if k in ("tp", "tn", "fp", "fn")} if threshold is not None else None
    # Participant-level bootstrap (rows of one child resampled together).
    by_participant: dict[str, list[int]] = {}
    for index, pid in enumerate(participants):
        by_participant.setdefault(pid, []).append(index)
    keys = list(by_participant)
    rng = random.Random(seed)
    samples: dict[str, list[float]] = {name: [] for name in estimate}
    for _ in range(bootstrap):
        indexes = [i for key in (rng.choice(keys) for _ in keys) for i in by_participant[key]]
        lab, sc = labels[indexes], scores[indexes]
        if len(set(lab.tolist())) < 2:
            continue
        for name, value in point(lab, sc).items():
            if value is not None:
                samples[name].append(value)
    intervals = {name: [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))] if len(vals) >= 100 else None for name, vals in samples.items()}
    bins = np.linspace(0, 1, 6)
    calibration = []
    for low, high in zip(bins[:-1], bins[1:]):
        mask = (scores >= low) & (scores < high if high < 1 else scores <= high)
        if mask.any():
            calibration.append({"bin": [float(low), float(high)], "n": int(mask.sum()), "mean_score": float(scores[mask].mean()), "observed_rate": float(labels[mask].mean())})
    counts = {"rows": int(len(labels)), "participants": len(keys), "positive_rows": int(labels.sum()), "negative_rows": int(len(labels) - labels.sum())}
    return {"estimate": estimate, "ci95": intervals, "confusion_at_threshold": confusion, "counts": counts, "calibration_bins": calibration}


def _feature_reference(x: np.ndarray) -> dict[str, dict[str, float | None]]:
    """Training-partition distribution per feature (for out-of-range checks and explanations)."""
    reference: dict[str, dict[str, float | None]] = {}
    for column, name in enumerate(FEATURE_NAMES):
        values = x[~np.isnan(x[:, column]), column]
        if not len(values):
            reference[name] = {"available_fraction": 0.0, "median": None, "p01": None, "p99": None}
            continue
        reference[name] = {
            "available_fraction": round(float(len(values) / len(x)), 4),
            "median": float(np.median(values)),
            "p01": float(np.percentile(values, 1)),
            "p99": float(np.percentile(values, 99)),
        }
    return reference


def train_screening_model(
    raw_rows: list[dict[str, Any]],
    output_dir: Path,
    *,
    training_data: str,
    provenance: dict[str, Any],
    model_id: str,
    version: str,
    seed: int = 42,
    candidate_sensitivity: float = 0.85,
) -> dict[str, Any]:
    if training_data not in ("synthetic", "real"):
        raise ValueError("training_data must be 'synthetic' or 'real'")
    if training_data == "real":
        missing = [key for key in REQUIRED_PROVENANCE if not provenance.get(key)]
        if missing:
            raise ValueError(f"Real-data training requires provenance fields: {missing}")
    rows, excluded = prepare_rows(raw_rows)
    if len({row.label for row in rows}) < 2:
        raise ValueError("Both outcome classes are required")
    split = grouped_split(rows, seed)
    x_train, y_train = _matrix(split["train"])
    x_val, y_val = _matrix(split["validation"])
    x_test, y_test = _matrix(split["test"])
    for name, labels in (("train", y_train), ("validation", y_val), ("test", y_test)):
        if len(set(labels.tolist())) < 2:
            raise ValueError(f"The {name} partition lacks one outcome class; more participants are needed")
    leakage = check_leakage(x_train, y_train, FEATURE_NAMES)

    # Hyper-parameter / model selection on validation only.
    selection = []
    best = None
    for algorithm, params, pipeline in _candidates(seed):
        pipeline.fit(x_train, y_train)
        val_auc = _auc(y_val, pipeline.predict_proba(x_val)[:, 1])
        selection.append({"algorithm": algorithm, "hyperparameters": params, "validation_roc_auc": val_auc})
        if algorithm != "dummy_prior" and val_auc is not None and (best is None or val_auc > best[0]):
            best = (val_auc, algorithm, params, pipeline)
    if best is None:
        raise ValueError("No candidate could be evaluated on the validation partition")
    _, algorithm, params, pipeline = best
    dummy = next(p for a, _, p in _candidates(seed) if a == "dummy_prior").fit(x_train, y_train)

    val_participants = {row.participant_id for row in split["validation"]}
    can_calibrate = len(val_participants) >= MIN_CALIBRATION_PARTICIPANTS and min(int(y_val.sum()), int(len(y_val) - y_val.sum())) >= MIN_CALIBRATION_PER_CLASS
    if can_calibrate:
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.frozen import FrozenEstimator

        pipeline = CalibratedClassifierCV(FrozenEstimator(pipeline), method="sigmoid").fit(x_val, y_val)
    output_type = "calibrated_probability" if can_calibrate else "research_score"

    val_scores = pipeline.predict_proba(x_val)[:, 1]
    candidate_threshold = _threshold_for_sensitivity(y_val, val_scores, candidate_sensitivity)
    test_scores = pipeline.predict_proba(x_test)[:, 1]
    train_eval = evaluate(y_train, pipeline.predict_proba(x_train)[:, 1], [r.participant_id for r in split["train"]], candidate_threshold, seed, bootstrap=200)
    # Calibration is fitted on validation, so validation metrics after calibration are optimistic.
    val_eval = evaluate(y_val, val_scores, [r.participant_id for r in split["validation"]], candidate_threshold, seed, bootstrap=200)
    test_participants = [row.participant_id for row in split["test"]]
    evaluation = evaluate(y_test, test_scores, test_participants, candidate_threshold, seed)
    dummy_eval = evaluate(y_test, dummy.predict_proba(x_test)[:, 1], test_participants, None, seed, bootstrap=200)
    n_test_participants = len(set(test_participants))
    reliable = n_test_participants >= MIN_RELIABLE_TEST_PARTICIPANTS and int(y_test.sum()) >= MIN_RELIABLE_TEST_POSITIVES

    synthetic = training_data == "synthetic"
    target_id, target_definition = (RESEARCH_TARGET_ID, RESEARCH_TARGET_DEFINITION) if synthetic else (TARGET_ID, TARGET_DEFINITION)
    model = ScreeningModel(pipeline, FEATURE_NAMES, SCREENING_SCHEMA_VERSION, target_id, training_data, output_type, algorithm, params)  # type: ignore[arg-type]
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / "model.pkl"
    artifact.write_bytes(pickle.dumps(model))
    card = {
        "model_id": model_id,
        "version": version,
        "name": f"Dyscover synthetic research predictor ({algorithm})" if synthetic else f"Dyscover reading-difficulty screening ({algorithm})",
        # synthetic_research models are only ever served by the research route.
        "designation": "synthetic_research" if synthetic else "clinical_screening_candidate",
        "target_id": target_id,
        "target_definition": target_definition,
        "feature_schema_version": SCREENING_SCHEMA_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "training_data": training_data,
        "output_type": output_type,
        "algorithm": algorithm,
        "hyperparameters": params,
        "artifact": artifact.name,
        "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "runtime": runtime_info(),
        "training_config": {
            "split": "StratifiedGroupKFold by participant: 1/5 test, then 1/4 of the remainder validation",
            "imputation": "median + missingness indicators, fitted on the training partition only",
            "calibration": "sigmoid on validation (FrozenEstimator)" if can_calibrate else f"not fitted: validation needs >= {MIN_CALIBRATION_PARTICIPANTS} participants and >= {MIN_CALIBRATION_PER_CLASS} rows per class",
            "selection_criterion": SELECTION_CRITERION,
            "leakage_auc_limit": LEAKAGE_AUC_LIMIT,
        },
        "leakage_check": {"univariate_train_auc": leakage, "passed": True},
        "feature_reference": _feature_reference(x_train),
        "provenance": provenance,
        "data_summary": {
            "rows_used": len(rows),
            "rows_excluded": excluded,
            "participants": {name: len({r.participant_id for r in part}) for name, part in split.items()},
            "positives": {name: int(sum(r.label for r in part)) for name, part in split.items()},
        },
        "model_selection": selection,
        "evaluation": {
            "train": train_eval,
            "validation": val_eval,
            "test": evaluation,
            "dummy_baseline_test": dummy_eval["estimate"],
            "selected_beats_baseline": (evaluation["estimate"]["roc_auc"] or 0) > (dummy_eval["estimate"]["roc_auc"] or 0.5),
            "reliable_sample_size": reliable,
            "reliability_note": None if reliable else f"Test set has {n_test_participants} participants / {int(y_test.sum())} positives; below {MIN_RELIABLE_TEST_PARTICIPANTS}/{MIN_RELIABLE_TEST_POSITIVES}. Metrics are unstable and are not evidence of performance.",
        },
        # What an assessment must contain before the research route scores it. The simulator
        # does not model age; 4-10 is the product's intended range, not a validated one.
        "research_inputs": {
            "min_scored_trials": 15,
            "required_features": ["overall_accuracy", "median_reaction_time_ms", "completion_rate", *(n for n in FEATURE_NAMES if n.startswith("domain_"))],
            "languages": ["en"],
            "age_min": 4,
            "age_max": 10,
        } if synthetic else None,
        # A threshold proposal only. It becomes an operating threshold only when a
        # qualified reviewer approves it in ``validation.approved_thresholds``.
        "candidate_threshold": {"value": candidate_threshold, "rule": f"validation sensitivity >= {candidate_sensitivity}", "status": "requires_specialist_approval"},
        # Filled in by humans after independent review; training never sets these.
        "validation": {
            "held_out_participant_evaluation": True,
            "external_validation_reference": None,
            "specialist_review_reference": None,
            "ethics_approval_reference": None,
            "approved_thresholds": [],
            "intended_population": {"age_min": None, "age_max": None, "languages": []},
            "min_scored_trials": 15,
        },
    }
    (output_dir / "model_card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    return card


# --- data sources -------------------------------------------------------------------

def load_csv(path: Path) -> list[dict[str, Any]]:
    """CSV columns: participant_id, label (0/1), then any of the schema feature names."""
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        for record in csv.DictReader(handle):
            features = {name: (float(record[name]) if record.get(name) not in (None, "") else None) for name in FEATURE_NAMES}
            rows.append({"participant_id": record["participant_id"], "label": record["label"], "features": features})
    return rows


def synthetic_rows(seed: int, subjects: int) -> list[dict[str, Any]]:
    """Assessment-level synthetic rows (see ``research_data``); labels are simulator settings."""
    return generate_research_dataset(seed=seed, participants=subjects)["rows"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train a Dyscover screening model")
    parser.add_argument("--data", type=Path)
    parser.add_argument("--provenance", type=Path)
    parser.add_argument("--synthetic-demo", action="store_true")
    parser.add_argument("--subjects", type=int, default=800, help="synthetic participants (2 assessments each)")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-id", default="dyscover-screening")
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    if args.synthetic_demo:
        dataset = generate_research_dataset(seed=args.seed, participants=args.subjects)
        card = train_screening_model(
            dataset["rows"], args.output, training_data="synthetic",
            provenance={"source": "Dyscover simulator (app.ml.screening.research_data)", "license": "n/a", "dataset": dataset["metadata"], "note": "Synthetic research model. Labels are simulator settings, not clinical outcomes."},
            model_id="dyscover-research-synthetic" if args.model_id == "dyscover-screening" else args.model_id, version=args.version, seed=args.seed,
        )
    else:
        if not args.data or not args.provenance:
            parser.error("--data and --provenance are required for real-data training")
        card = train_screening_model(
            load_csv(args.data), args.output, training_data="real",
            provenance=json.loads(args.provenance.read_text(encoding="utf-8")),
            model_id=args.model_id, version=args.version, seed=args.seed,
        )
    evaluation = card["evaluation"]
    print(json.dumps({
        "model_id": card["model_id"], "version": card["version"], "algorithm": card["algorithm"], "hyperparameters": card["hyperparameters"],
        "output_type": card["output_type"], "artifact_sha256": card["artifact_sha256"], "model_selection": card["model_selection"],
        "train": evaluation["train"]["estimate"], "validation": evaluation["validation"]["estimate"], "test": evaluation["test"]["estimate"],
        "test_ci95": evaluation["test"]["ci95"], "test_confusion": evaluation["test"]["confusion_at_threshold"], "test_counts": evaluation["test"]["counts"],
        "dummy_baseline_test": evaluation["dummy_baseline_test"], "candidate_threshold": card["candidate_threshold"],
        "reliable_sample_size": evaluation["reliable_sample_size"], "leakage_check": card["leakage_check"], "data_summary": card["data_summary"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
