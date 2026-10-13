from collections import Counter
from math import sqrt
from typing import Any


def class_distribution(labels: list[Any]) -> dict[str, Any]:
    counts = Counter(str(label) for label in labels)
    total = len(labels)
    return {
        "counts": dict(counts),
        "minority_class_percentage": min(counts.values()) / total if counts and total else 0,
        "imbalance_ratio": (max(counts.values()) / min(counts.values()) if counts and min(counts.values()) else None),
    }


def regression_metrics(actual: list[float], predicted: list[float]) -> dict[str, float]:
    if not actual or len(actual) != len(predicted):
        return {}
    errors = [prediction - truth for truth, prediction in zip(actual, predicted)]
    mae = sum(abs(error) for error in errors) / len(errors)
    mse = sum(error * error for error in errors) / len(errors)
    mean_actual = sum(actual) / len(actual)
    total = sum((truth - mean_actual) ** 2 for truth in actual)
    return {"mae": mae, "mse": mse, "rmse": sqrt(mse), "r2": 1 - (sum(error * error for error in errors) / total) if total else 0.0}


def classification_metrics(actual: list[Any], predicted: list[Any]) -> dict[str, Any]:
    if not actual or len(actual) != len(predicted):
        return {}
    labels = sorted(set(actual) | set(predicted))
    if len(labels) < 2:
        return {
            "accuracy": sum(a == p for a, p in zip(actual, predicted)) / len(actual),
            "balanced_accuracy": None,
            "precision": None,
            "recall": None,
            "f1": None,
        }
    if len(labels) == 2:
        positive = labels[-1]
        tp = sum(a == positive and p == positive for a, p in zip(actual, predicted))
        tn = sum(a != positive and p != positive for a, p in zip(actual, predicted))
        fp = sum(a != positive and p == positive for a, p in zip(actual, predicted))
        fn = sum(a == positive and p != positive for a, p in zip(actual, predicted))
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        negative_recall = tn / (tn + fp) if tn + fp else None
        f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
        return {
            "accuracy": (tp + tn) / len(actual),
            "balanced_accuracy": (recall + negative_recall) / 2 if recall is not None and negative_recall is not None else None,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    # Multiclass classification
    correct = sum(a == p for a, p in zip(actual, predicted))
    accuracy = correct / len(actual)
    per_class: dict[str, dict[str, float | int | None]] = {}
    recalls: list[float] = []
    f1s: list[float] = []
    precisions: list[float] = []
    for label in labels:
        tp = sum(a == label and p == label for a, p in zip(actual, predicted))
        fp = sum(a != label and p == label for a, p in zip(actual, predicted))
        fn = sum(a == label and p != label for a, p in zip(actual, predicted))
        support = sum(a == label for a in actual)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1_val = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        if support > 0:
            recalls.append(rec)
        precisions.append(prec)
        f1s.append(f1_val)
        per_class[str(label)] = {
            "precision": prec,
            "recall": rec,
            "f1": f1_val,
            "support": support,
        }

    balanced_accuracy = sum(recalls) / len(recalls) if recalls else None
    macro_f1 = sum(f1s) / len(f1s) if f1s else None
    macro_precision = sum(precisions) / len(precisions) if precisions else None
    return {
        "accuracy": accuracy,
        "balanced_accuracy": balanced_accuracy,
        "macro_f1": macro_f1,
        "precision": macro_precision,
        "recall": balanced_accuracy,
        "f1": macro_f1,
        "per_class": per_class,
    }
