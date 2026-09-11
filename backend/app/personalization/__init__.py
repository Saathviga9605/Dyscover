"""Stage 5 — Deterministic Personalization Engine.

Stage 5 is deterministic personalization, not machine-learned personalization.

This package turns real, persisted assessment observations (trials/events)
into transparent, rule-based outputs: skill profiles, evidence sufficiency,
relative performance categories, adaptive difficulty, activity
recommendations, and progress summaries.

Guarantees:
- Deterministic: identical input data + configuration => identical output.
- Versioned: every result carries the engine and configuration version.
- Non-diagnostic: categories describe observed activity only; no clinical
  probabilities, risk, diagnosis, or validated thresholds are produced.
- Modality-aware: behavior drives everything today; speech/gaze may later
  contribute independently without breaking behavioral personalization.
"""

PERSONALIZATION_ENGINE_VERSION = "1.0.0"
PERSONALIZATION_SCHEMA_VERSION = "1.0"

MODE = "DETERMINISTIC_OBSERVATION"