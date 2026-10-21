"""Multi-seed synthetic evaluation with leakage probes (research only).

    python -m app.ml.synthetic.experiment --seeds 1 2 3 4 5 --subjects 60 --output report.json

For every seed: generate a dataset, train every baseline on a subject-level split
and record held-out metrics. Two probes guard against misleadingly strong results:
- a label-permutation run (training labels shuffled) must fall to chance level;
- random-forest feature importances are reported so a single feature that encodes
  the simulator label would be visible.
Results describe how separable the *simulator's* profiles are. They say nothing about
real children or dyslexia.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import tempfile
from pathlib import Path
from typing import Any

from app.ml.datasets import subject_level_split
from app.ml.feature_registry import REGISTRY_BY_NAME

from .evaluation import evaluate_partition
from .generator import SyntheticConfig, generate_dataset
from .pipeline import get_synthetic_estimator, train_synthetic_models

ALGORITHMS = ("dummy", "logistic_regression", "random_forest", "gradient_boosting")


def _summary(values: list[float]) -> dict[str, float | None]:
    clean = [value for value in values if value is not None]
    if not clean:
        return {"mean": None, "sd": None, "min": None, "max": None}
    return {
        "mean": round(statistics.mean(clean), 4),
        "sd": round(statistics.stdev(clean), 4) if len(clean) > 1 else 0.0,
        "min": round(min(clean), 4),
        "max": round(max(clean), 4),
    }


def _permutation_probe(dataset: dict[str, Any], seed: int) -> dict[str, Any]:
    rows = [row for row in dataset["rows"] if row.get("eligible")]
    split = subject_level_split(rows, seed=seed)
    labels = [row["target"] for row in split["train"]]
    random.Random(seed).shuffle(labels)
    model = get_synthetic_estimator("random_forest", sorted(REGISTRY_BY_NAME))
    model.fit(split["train"], labels)
    classes = sorted({row["target"] for row in rows})
    metrics = evaluate_partition([row["target"] for row in split["test"]], model.predict(split["test"]), classes)
    return {"accuracy": metrics.get("accuracy"), "macro_f1": metrics.get("macro_f1"), "chance_level": round(1 / len(classes), 4)}


def _top_importances(output_dir: Path, limit: int = 8) -> list[tuple[str, float]]:
    import pickle

    with (output_dir / "random_forest.pkl").open("rb") as handle:
        model = pickle.load(handle)  # noqa: S301 - file produced by this run
    forest = model.pipeline.named_steps["model"]
    imputer = model.pipeline.named_steps["imputer"]
    names = list(imputer.get_feature_names_out(model.feature_names))
    ranked = sorted(zip(names, forest.feature_importances_), key=lambda item: item[1], reverse=True)
    return [(name, round(float(value), 4)) for name, value in ranked[:limit]]


def run(seeds: list[int], subjects: int) -> dict[str, Any]:
    per_seed: list[dict[str, Any]] = []
    for seed in seeds:
        dataset = generate_dataset(SyntheticConfig(seed=seed, subjects=subjects))
        with tempfile.TemporaryDirectory() as tmp:
            results = train_synthetic_models(dataset, Path(tmp), ALGORITHMS)
            importances = _top_importances(Path(tmp))
        evaluation = results["dummy"]["evaluation"]
        per_seed.append(
            {
                "seed": seed,
                "eligible_sessions": dataset["metadata"]["eligible_sessions"],
                "subjects": evaluation.get("partitions"),
                "classes": sorted(results["dummy"]["class_distribution"]["counts"]),
                "test": {algo: {k: results[algo]["evaluation"]["test_metrics"].get(k) for k in ("accuracy", "macro_f1", "support")} for algo in ALGORITHMS},
                "permutation_probe": _permutation_probe(dataset, seed),
                "random_forest_top_features": importances,
            }
        )
    aggregate = {
        algo: {
            "accuracy": _summary([run["test"][algo]["accuracy"] for run in per_seed]),
            "macro_f1": _summary([run["test"][algo]["macro_f1"] for run in per_seed]),
        }
        for algo in ALGORITHMS
    }
    aggregate["permuted_labels_random_forest"] = {
        "accuracy": _summary([run["permutation_probe"]["accuracy"] for run in per_seed]),
        "macro_f1": _summary([run["permutation_probe"]["macro_f1"] for run in per_seed]),
    }
    return {
        "purpose": "Separability of simulator-defined synthetic profiles. Not a measure of real-world or clinical performance.",
        "seeds": seeds,
        "subjects_per_seed": subjects,
        "aggregate_test_metrics": aggregate,
        "per_seed": per_seed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    parser.add_argument("--subjects", type=int, default=60)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = run(args.seeds, args.subjects)
    text = json.dumps(report, indent=2, default=str)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(json.dumps(report["aggregate_test_metrics"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
