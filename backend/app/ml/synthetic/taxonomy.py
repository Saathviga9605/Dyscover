"""Taxonomy of simulated interaction profiles.

This taxonomy defines software-simulated behavioral interaction patterns for ML
research and classification pipeline evaluation.

IMPORTANT NOTICE:
These labels describe simulator-defined synthetic behavior profiles only. They DO NOT
represent clinical dyslexia diagnoses, dyslexia screening results, or diagnostic categories.
Models trained on these profiles evaluate whether machine learning algorithms can recover
known synthetic simulation mechanisms from game interaction features under documented
assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ScenarioProfile:
    name: str
    display_name: str
    operational_definition: str
    target_accuracy_range: tuple[float, float]
    mean_reaction_time_ms: float
    reaction_time_variance_ms2: float
    hesitation_mean_ms: float
    error_rate_range: tuple[float, float]
    simulation_assumptions: str
    eligible_for_training: bool = True


PROFILES: dict[str, ScenarioProfile] = {
    "consistent_responses": ScenarioProfile(
        name="consistent_responses",
        display_name="Consistent Responses Profile",
        operational_definition=(
            "Simulated interaction demonstrating high overall accuracy (mean >= 0.90), "
            "stable and prompt reaction times (mean ~750ms, low variance ~180ms^2), "
            "minimal hesitation (< 100ms), and near-zero pauses or hints. All sessions complete."
        ),
        target_accuracy_range=(0.88, 0.98),
        mean_reaction_time_ms=750.0,
        reaction_time_variance_ms2=180.0,
        hesitation_mean_ms=70.0,
        error_rate_range=(0.02, 0.12),
        simulation_assumptions="Assumes steady motor engagement and high familiarity with game tasks across all modalities.",
        eligible_for_training=True,
    ),
    "variable_response_timing": ScenarioProfile(
        name="variable_response_timing",
        display_name="Variable Response Timing Profile",
        operational_definition=(
            "Simulated interaction with satisfactory task accuracy (mean ~0.82), but elevated "
            "and fluctuating latency (mean ~1100ms, variance ~1100ms^2), with wider hesitation spread. "
            "Response completion remains high."
        ),
        target_accuracy_range=(0.76, 0.90),
        mean_reaction_time_ms=1100.0,
        reaction_time_variance_ms2=1100.0,
        hesitation_mean_ms=160.0,
        error_rate_range=(0.10, 0.24),
        simulation_assumptions="Assumes latency fluctuations per trial due to variable deliberation time or motor pacing, without a general accuracy collapse.",
        eligible_for_training=True,
    ),
    "high_error_frequency": ScenarioProfile(
        name="high_error_frequency",
        display_name="High Error Frequency Profile",
        operational_definition=(
            "Simulated interaction exhibiting frequent incorrect responses across all game types "
            "(accuracy mean ~0.45, error rate >= 0.50), prolonged reaction times (~1250ms), "
            "and elevated total error counts across completed trials."
        ),
        target_accuracy_range=(0.35, 0.55),
        mean_reaction_time_ms=1250.0,
        reaction_time_variance_ms2=350.0,
        hesitation_mean_ms=180.0,
        error_rate_range=(0.45, 0.65),
        simulation_assumptions="Assumes widespread task confusion or guessing behavior across multiple cognitive domains.",
        eligible_for_training=True,
    ),
    "repeated_symbol_confusions": ScenarioProfile(
        name="repeated_symbol_confusions",
        display_name="Repeated Symbol Confusions Profile",
        operational_definition=(
            "Simulated interaction showing selective error concentration on visual symbol discrimination "
            "tasks (Letter Detective and Mirror Match, e.g. b/d/p/q confusions), with reduced accuracy "
            "(~0.55) and higher hesitation on these tasks, while working memory and speech tasks remain unaffected."
        ),
        target_accuracy_range=(0.50, 0.68),
        mean_reaction_time_ms=1050.0,
        reaction_time_variance_ms2=900.0,
        hesitation_mean_ms=210.0,
        error_rate_range=(0.32, 0.50),
        simulation_assumptions="Assumes localized challenge in distinguishing mirror-image glyphs and similarly shaped letters in visual tasks.",
        eligible_for_training=True,
    ),
    "reduced_reading_response_coverage": ScenarioProfile(
        name="reduced_reading_response_coverage",
        display_name="Reduced Reading Response Coverage Profile",
        operational_definition=(
            "Simulated interaction where visual game performance is normal (~0.80), but speech-based reading "
            "tasks exhibit incomplete observation coverage (e.g. missing ASR transcripts, speech_available=0, "
            "or low word-count observations)."
        ),
        target_accuracy_range=(0.72, 0.85),
        mean_reaction_time_ms=900.0,
        reaction_time_variance_ms2=800.0,
        hesitation_mean_ms=150.0,
        error_rate_range=(0.15, 0.28),
        simulation_assumptions="Assumes microphone capture dropout, low vocal volume, or unparsed speech telemetry during reading tasks.",
        eligible_for_training=True,
    ),
    "attention_variability": ScenarioProfile(
        name="attention_variability",
        display_name="Attention Variability Profile",
        operational_definition=(
            "Simulated interaction characterized by frequent mid-session pauses (pause_count >= 3), "
            "multiple hint requests, high reaction-time variance (~1800ms^2), and elevated distractor fixation times."
        ),
        target_accuracy_range=(0.60, 0.76),
        mean_reaction_time_ms=1150.0,
        reaction_time_variance_ms2=1800.0,
        hesitation_mean_ms=220.0,
        error_rate_range=(0.24, 0.40),
        simulation_assumptions="Assumes attentional lapses and task disengagement leading to intermittent long latencies and pause interactions.",
        eligible_for_training=True,
    ),
    "working_memory_task_difficulty": ScenarioProfile(
        name="working_memory_task_difficulty",
        display_name="Working Memory Task Difficulty Profile",
        operational_definition=(
            "Simulated interaction where performance degrades selectively on sequential memory tasks "
            "(Sequence Quest), particularly as sequence length increases from 3 to 6 items (accuracy ~0.45 "
            "on Sequence Quest, but >= 0.85 on single-symbol Letter Detective and Mirror Match)."
        ),
        target_accuracy_range=(0.65, 0.78),
        mean_reaction_time_ms=1000.0,
        reaction_time_variance_ms2=950.0,
        hesitation_mean_ms=180.0,
        error_rate_range=(0.22, 0.35),
        simulation_assumptions="Assumes span capacity limitation that affects multi-step sequence reproduction without affecting single-item recognition.",
        eligible_for_training=True,
    ),
    "mixed_interaction_profile": ScenarioProfile(
        name="mixed_interaction_profile",
        display_name="Mixed Interaction Profile",
        operational_definition=(
            "Simulated interaction showing moderate, balanced performance across accuracy (~0.70), "
            "response speed (~980ms), and error counts without a single dominating behavioral bottleneck."
        ),
        target_accuracy_range=(0.64, 0.76),
        mean_reaction_time_ms=980.0,
        reaction_time_variance_ms2=750.0,
        hesitation_mean_ms=150.0,
        error_rate_range=(0.24, 0.36),
        simulation_assumptions="Assumes typical mixed engagement with intermediate response accuracy and timing across diverse tasks.",
        eligible_for_training=True,
    ),
    "insufficient_observations": ScenarioProfile(
        name="insufficient_observations",
        display_name="Insufficient Observations Profile",
        operational_definition=(
            "Simulated session with incomplete evidence: fewer than 2 completed trials, aborted session state, "
            "or low completion rate (< 0.50). Ineligible for model training splits."
        ),
        target_accuracy_range=(0.40, 0.60),
        mean_reaction_time_ms=900.0,
        reaction_time_variance_ms2=600.0,
        hesitation_mean_ms=250.0,
        error_rate_range=(0.40, 0.60),
        simulation_assumptions="Assumes session abandonment, network dropout, or premature exit resulting in insufficient evidence for feature extraction.",
        eligible_for_training=False,
    ),
}

SCENARIO_DEFINITIONS: dict[str, dict[str, str]] = {
    name: {
        "definition": profile.operational_definition,
        "display_name": profile.display_name,
        "simulation_assumptions": profile.simulation_assumptions,
        "eligible_for_training": str(profile.eligible_for_training),
    }
    for name, profile in PROFILES.items()
}

SUPPORTED_SCENARIOS: tuple[str, ...] = tuple(PROFILES.keys())
ELIGIBLE_SCENARIOS: tuple[str, ...] = tuple(name for name, p in PROFILES.items() if p.eligible_for_training)

