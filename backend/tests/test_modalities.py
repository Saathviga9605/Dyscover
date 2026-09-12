"""Multimodal feature-extraction tests (Z through AE).

Verifies that behavior, gaze, and speech modalities compose in the shared
feature architecture, that missing modalities are explicit, and that adding a
modality never changes behavior evidence semantics.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ml.features import extract_session_features
from app.ml.profile import build_profile
from app.ml.validation import build_quality_report


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


class _Trial:
    def __init__(self, correct: bool = True, reaction: int = 800, domain: str = "accuracy", completed: bool = True, score: float = 1.0):
        self.id = "t1"
        self.game_session_id = "g1"
        self.completed_at = True if completed else None
        self.correctness = correct
        self.reaction_time_ms = reaction
        self.hesitation_time_ms = 100
        self.error_count = 0
        self.score = score
        self.started_at = 1
        self.domain = domain


class _Game:
    id = "g1"
    game_id = "letter-detective"


_GAZE = {
    "gaze_sample_count": 12,
    "gaze_fixation_count": 3,
    "gaze_mean_fixation_duration_ms": 180,
    "gaze_max_fixation_duration_ms": 220,
    "gaze_target_fixation_time_ms": 300,
    "gaze_distractor_fixation_time_ms": 240,
    "gaze_time_to_first_target_fixation_ms": 150,
    "gaze_fixation_switch_count": 2,
    "gaze_regression_count": 1,
    "gaze_saccade_variance_ms2": 2500.0,
    "gaze_scanpath_entropy": 0.9,
    "gaze_horizontal_saccade_bias": 0.4,
    "gaze_coverage_ratio": 0.5,
}

_SPEECH_FEATURES = {
    "speech_reading_duration_ms": {"value": 4200, "available": True, "modality": "speech"},
    "speech_words_per_minute": {"value": 57.0, "available": True, "modality": "speech"},
    "speech_error_rate": {"value": 0.0, "available": True, "modality": "speech"},
    "speech_substitution_count": {"value": 0, "available": True, "modality": "speech"},
    "text_token_count": {"value": 4, "available": True, "modality": "text"},
}


def _behavior_trials():
    return [_Trial(), _Trial(correct=True, reaction=900), _Trial(correct=False, reaction=1200, score=0.0)]


def test_z_behavior_only_modalities(client: TestClient) -> None:
    features, _ = extract_session_features(None, [_Game()], _behavior_trials(), [])
    profile = build_profile("s1", features, {"trial_count": 3, "feature_schema_version": "1.0"})
    assert profile["available_modalities"] == ["behavior"]
    assert features["speech_available"]["value"] is None
    assert features["speech_available"]["available"] is False


def test_aa_gaze_adds_gaze_features(client: TestClient) -> None:
    features, _ = extract_session_features(None, [_Game()], _behavior_trials(), [], gaze_features=_GAZE)
    assert features["gaze_available"]["value"] == 1
    assert features["gaze_fixation_count"]["value"] == 3
    assert features["gaze_mean_fixation_duration_ms"]["value"] == 180
    profile = build_profile("s1", features, {"trial_count": 3, "feature_schema_version": "1.0"})
    assert "gaze" in profile["available_modalities"]
    assert any("eye-movement" in item.lower() for item in profile["observations"])


def test_ab_speech_adds_speech_features(client: TestClient) -> None:
    speech = [{"features": _SPEECH_FEATURES, "language": "en"}]
    features, _ = extract_session_features(None, [_Game()], _behavior_trials(), [], speech_sessions=speech)
    assert features["speech_available"]["value"] == 1
    assert features["speech_words_per_minute"]["value"] == 57.0
    profile = build_profile("s1", features, {"trial_count": 3, "feature_schema_version": "1.0"})
    assert "speech" in profile["available_modalities"]


def test_ac_all_three_modalities_coexist(client: TestClient) -> None:
    speech = [{"features": _SPEECH_FEATURES, "language": "en"}]
    features, _ = extract_session_features(None, [_Game()], _behavior_trials(), [], gaze_features=_GAZE, speech_sessions=speech)
    profile = build_profile("s1", features, {"trial_count": 3, "feature_schema_version": "1.0"})
    assert set(profile["available_modalities"]) == {"behavior", "gaze", "speech", "text"}
    assert features["overall_accuracy"]["value"] == pytest.approx(2 / 3)


def test_ad_missing_speech_is_explicit_not_zero(client: TestClient) -> None:
    features, _ = extract_session_features(None, [_Game()], _behavior_trials(), [])
    assert features["speech_available"]["value"] is None
    for name in ("speech_reading_duration_ms", "speech_error_rate", "text_token_count"):
        assert features[name]["available"] is False
        assert features[name]["value"] is None
    missing_speech = [{"features": {"speech_reading_duration_ms": {"value": None, "available": False}}, "language": "en"}]
    features, _ = extract_session_features(None, [_Game()], _behavior_trials(), [], speech_sessions=missing_speech)
    assert features["speech_available"]["value"] == 0
    profile = build_profile("s1", features, {"trial_count": 3, "feature_schema_version": "1.0"})
    assert any("no recognized speech" in item.lower() for item in profile["observations"])


def test_ae_behavior_evidence_unchanged_by_modalities(client: TestClient) -> None:
    behavior_only, _ = extract_session_features(None, [_Game()], _behavior_trials(), [])
    multimodal, _ = extract_session_features(None, [_Game()], _behavior_trials(), [], gaze_features=_GAZE, speech_sessions=[{"features": _SPEECH_FEATURES}])
    for name in ("overall_accuracy", "mean_reaction_time_ms", "completion_rate", "total_error_count"):
        assert behavior_only[name]["value"] == multimodal[name]["value"]
        assert behavior_only[name]["modality"] == "behavior"


def test_ae2_quality_report_computes_modality_availability(client: TestClient) -> None:
    session = type("S", (), {"completed_at": True, "games": [1], "id": "a"})()
    report = build_quality_report(
        [session],
        [_Trial(), _Trial(), _Trial()],
        gaze_trial_ids={"t1"},
        speech_trial_ids={"t1", "t2"},
    )
    assert report["gaze_availability"] == pytest.approx(1 / 3)
    assert report["speech_availability"] == pytest.approx(2 / 3)