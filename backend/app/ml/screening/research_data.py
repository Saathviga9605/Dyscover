"""Synthetic *assessment-level* research dataset for the screening-1.0 schema.

Why a separate generator: the original simulator (``app.ml.synthetic``) emits one
row per single-game session, which never contains the four per-domain accuracies
of the screening schema. A real Dyscover visual run is one assessment of five
games (22 trials across four domains), so this module composes simulated trials
into that exact structure and derives the 15 features with the same formulas as
``app.ml.features.extract_session_features``.

Label-generation rule (documented in docs/readiness/ai-ml-validation.md §9):
each synthetic participant is assigned one simulator profile (cycled, so the
eight trainable profiles are balanced); the label is 1 when that profile is in
``POSITIVE_PROFILES`` and 0 otherwise. All trials are drawn from the profile's
parameters (accuracy range, reaction-time mean/variance, hesitation). The label
is therefore a deterministic function of simulator settings that also generate
the features — models trained here learn to recover those settings, nothing
about children. Labels are not clinical ground truth.
"""

from __future__ import annotations

import hashlib
import json
from random import Random
from statistics import mean, median, pvariance
from typing import Any

from app.ml.synthetic.games import GAME_DOMAINS
from app.ml.synthetic.modalities import simulate_gaze_features
from app.ml.synthetic.simulator import simulate_trial_sequence
from app.ml.synthetic.taxonomy import PROFILES

from .schema import FEATURE_NAMES, VISUAL_DOMAINS

DATASET_VERSION = "screening-synthetic-assessments-1.0"
RESEARCH_TARGET_ID = "synthetic_reading_difficulty_profile_v1"
RESEARCH_TARGET_DEFINITION = (
    "Synthetic target: 1 when the Dyscover simulator generated the participant from one of the "
    "profiles high_error_frequency, repeated_symbol_confusions, reduced_reading_response_coverage "
    "or working_memory_task_difficulty; 0 for the other trainable simulator profiles. It is a "
    "simulator setting chosen by developers, not a clinical label, and not a dyslexia diagnosis."
)
POSITIVE_PROFILES = frozenset({"high_error_frequency", "repeated_symbol_confusions", "reduced_reading_response_coverage", "working_memory_task_difficulty"})
TRAINABLE_PROFILES = tuple(name for name, profile in PROFILES.items() if profile.eligible_for_training and name != "insufficient_observations")

# The visual run exactly as the app plays it (frontend GameRunner: trials per game).
VISUAL_RUN: tuple[tuple[str, int], ...] = (
    ("letter-detective", 5),
    ("mirror-match", 5),
    ("word-flash", 5),
    ("sequence-quest", 4),
    ("word-maze", 3),
)


def assessment_features(trials: list[dict[str, Any]], gaze: dict[str, Any] | None) -> dict[str, float | None]:
    """Screening features from simulated trials, mirroring ``extract_session_features``."""
    correctness = [t["correctness"] for t in trials if t["correctness"] is not None]
    reactions = [t["reaction_time_ms"] for t in trials]
    hesitations = [t["hesitation_time_ms"] for t in trials]
    features: dict[str, float | None] = {name: None for name in FEATURE_NAMES}
    features["overall_accuracy"] = mean(correctness) if correctness else None
    features["median_reaction_time_ms"] = median(reactions) if reactions else None
    features["reaction_time_variance_ms2"] = pvariance(reactions) if len(reactions) > 1 else None
    features["mean_hesitation_time_ms"] = mean(hesitations) if hesitations else None
    # Simulated runs only contain answered trials, as stored by the app.
    features["completion_rate"] = 1.0 if trials else None
    for domain in VISUAL_DOMAINS:
        values = [t["correctness"] for t in trials if t["domain"] == domain and t["correctness"] is not None]
        features[f"domain_{domain}_accuracy"] = mean(values) if values else None
    if gaze:
        features["gaze_regression_count"] = gaze.get("gaze_regression_count")
        features["gaze_mean_fixation_duration_ms"] = gaze.get("gaze_mean_fixation_duration_ms")
    # Speech features stay missing: the visual run records no read-aloud speech.
    return features


def generate_research_dataset(seed: int = 42, participants: int = 800, assessments_per_participant: int = 2, gaze_availability: float = 0.3) -> dict[str, Any]:
    """Deterministic for a given seed and configuration (checksum recorded in metadata)."""
    if participants < len(TRAINABLE_PROFILES) or assessments_per_participant < 1:
        raise ValueError("need at least one participant per profile and one assessment each")
    rng = Random(seed)
    rows: list[dict[str, Any]] = []
    for index in range(participants):
        # Neutral identifiers: nothing about the profile is encoded in the ID.
        participant_id = f"synthetic-participant-{index:05d}"
        profile = TRAINABLE_PROFILES[index % len(TRAINABLE_PROFILES)]
        for _ in range(assessments_per_participant):
            trials: list[dict[str, Any]] = []
            for game, count in VISUAL_RUN:
                simulated, _complete = simulate_trial_sequence(rng, profile, game, count, rng.randint(1, 3))
                trials.extend({**trial, "domain": GAME_DOMAINS[game]} for trial in simulated)
            gaze = None
            if rng.random() < gaze_availability:
                gaze = {name: record["value"] for name, record in simulate_gaze_features(rng, True, profile, "1.0").items()}
            rows.append({"participant_id": participant_id, "label": int(profile in POSITIVE_PROFILES), "features": assessment_features(trials, gaze), "synthetic": True})
    checksum = hashlib.sha256(json.dumps([[r["participant_id"], r["label"], r["features"]] for r in rows], sort_keys=True).encode()).hexdigest()
    metadata = {
        "dataset_version": DATASET_VERSION,
        "synthetic": True,
        "seed": seed,
        "participants": participants,
        "assessments_per_participant": assessments_per_participant,
        "gaze_availability": gaze_availability,
        "visual_run": [list(item) for item in VISUAL_RUN],
        "positive_profiles": sorted(POSITIVE_PROFILES),
        "negative_profiles": sorted(set(TRAINABLE_PROFILES) - POSITIVE_PROFILES),
        "target_id": RESEARCH_TARGET_ID,
        "rows": len(rows),
        "positive_rows": sum(r["label"] for r in rows),
        "data_checksum": checksum,
    }
    return {"metadata": metadata, "rows": rows}
