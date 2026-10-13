"""Command-line interface for the synthetic data generator and classification pipeline.

Usage examples:
  python -m app.ml.synthetic.cli --subjects 27 --output artifacts/synthetic/dataset.json
  python -m app.ml.synthetic.cli --subjects 27 --train-output artifacts/synthetic/models
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .games import SUPPORTED_GAMES, SUPPORTED_LANGUAGES
from .generator import (
    SIMULATOR_VERSION,
    SYNTHETIC_SCHEMA_VERSION,
    SyntheticConfig,
    export_dataset,
    generate_dataset,
)
from .pipeline import train_synthetic_models
from .taxonomy import SUPPORTED_SCENARIOS


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dyscover Synthetic Interaction Data Generator & ML Classification Pipeline (Research Only)"
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic generation")
    parser.add_argument("--subjects", type=int, default=27, help="Number of simulated subjects")
    parser.add_argument("--sessions-per-subject", type=int, default=2, help="Sessions per subject")
    parser.add_argument("--trials-per-session", type=int, default=5, help="Trials per session")
    parser.add_argument(
        "--games",
        nargs="+",
        default=list(SUPPORTED_GAMES),
        help=f"Games to simulate (choices: {', '.join(SUPPORTED_GAMES)})",
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        default=["en"],
        help=f"Languages to simulate (choices: {', '.join(SUPPORTED_LANGUAGES)})",
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        default=list(SUPPORTED_SCENARIOS),
        help=f"Scenarios to include (choices: {', '.join(SUPPORTED_SCENARIOS)})",
    )
    parser.add_argument(
        "--modality-availability",
        type=float,
        default=0.7,
        help="Proportion of sessions with optional modalities enabled (0.0 to 1.0)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Destination path to export generated dataset JSON",
    )
    parser.add_argument(
        "--train-output",
        type=Path,
        default=None,
        help="Directory to save trained model artifacts and evaluation metrics",
    )
    parser.add_argument(
        "--algorithms",
        nargs="+",
        default=["dummy", "logistic_regression", "random_forest", "gradient_boosting"],
        help="Model algorithms to train (choices: dummy, logistic_regression, random_forest, gradient_boosting)",
    )
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> int:
    parsed = parse_args(args)
    config = SyntheticConfig(
        seed=parsed.seed,
        subjects=parsed.subjects,
        sessions_per_subject=parsed.sessions_per_subject,
        trials_per_session=parsed.trials_per_session,
        games=tuple(parsed.games),
        languages=tuple(parsed.languages),
        scenarios=tuple(parsed.scenarios),
        modality_availability=parsed.modality_availability,
    )

    print(f"[Dyscover Synthetic ML] Generating dataset (seed={config.seed}, subjects={config.subjects})...")
    dataset = generate_dataset(config)
    meta = dataset["metadata"]
    print(f"Generated {meta['sessions']} sessions ({meta['eligible_sessions']} eligible) across {meta['subjects']} subjects.")
    print(f"Dataset Checksum: {meta['data_checksum']}")

    if parsed.output:
        out_path = parsed.output
        if out_path.exists():
            out_path.unlink()
        export_dataset(dataset, out_path)
        print(f"Exported dataset to: {out_path}")

    if parsed.train_output:
        print(f"[Dyscover Synthetic ML] Training algorithms: {parsed.algorithms}...")
        results = train_synthetic_models(dataset, parsed.train_output, tuple(parsed.algorithms))
        print(f"Training completed. Models saved to: {parsed.train_output}")
        for algo, res in results.items():
            test_acc = res["evaluation"]["test_metrics"].get("accuracy")
            macro_f1 = res["evaluation"]["test_metrics"].get("macro_f1")
            acc_str = f"{test_acc:.3f}" if test_acc is not None else "N/A"
            f1_str = f"{macro_f1:.3f}" if macro_f1 is not None else "N/A"
            print(f"  - {algo}: Test Acc={acc_str}, Macro-F1={f1_str}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
