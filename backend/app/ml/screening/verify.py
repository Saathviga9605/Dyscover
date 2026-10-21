"""Verify installed screening and research artifacts in a fresh process.

    python -m app.ml.screening.verify [--research-dir DIR] [--screening-dir DIR]

Loads every model card, checks the artifact checksum and runtime compatibility,
reports which registry (if any) may serve it and why not, and scores one
fixed, clearly artificial input to prove the estimator runs. Exit code 1 if no
research model is usable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import get_settings

from .registry import load_registry, load_research_registry

# Not a child: a fixed input used only to check that the loaded estimator runs.
PROBE = {"overall_accuracy": 0.75, "median_reaction_time_ms": 1000.0, "completion_rate": 1.0}


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--research-dir", type=Path, default=Path(settings.research_demo_model_dir))
    parser.add_argument("--screening-dir", type=Path, default=Path(settings.screening_model_dir))
    args = parser.parse_args(argv)

    def describe(entry) -> dict:
        return {
            "model_id": entry.model_id,
            "version": entry.version,
            "artifact_sha256": entry.card.get("artifact_sha256"),
            "usable": entry.eligible,
            "reasons": entry.reasons,
            "probe_score": entry.model.score([PROBE])[0] if entry.model is not None else None,
        }

    research = [describe(entry) for entry in load_research_registry(args.research_dir)]
    screening = [describe(entry) for entry in load_registry(args.screening_dir)]
    print(json.dumps({"research_dir": str(args.research_dir), "research_models": research, "screening_dir": str(args.screening_dir), "screening_models": screening, "research_mode_enabled": settings.research_demo_enabled}, indent=2))
    return 0 if any(item["usable"] for item in research) else 1


if __name__ == "__main__":
    raise SystemExit(main())
