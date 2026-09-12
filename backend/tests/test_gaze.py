"""Gaze observation tests (A through Q).

Covers the gaze ingest boundary, quality/sanitization, deterministic feature
extraction, registry integration, and the no-raw-media privacy boundary.
"""

import pytest
from fastapi.testclient import TestClient

from app.gaze.features import aggregate_gaze_features, analyze_fixations
from app.main import app
from app.ml.feature_registry import REGISTRY_BY_NAME


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _setup(client: TestClient) -> dict:
    child = client.post("/api/children", json={"display_name": "Explorer", "birth_year": 2018})
    assessment = client.post("/api/assessments", json={"child_id": child.json()["id"], "version": "stage-2.0"}).json()
    trial = client.post(
        f"/api/assessments/{assessment['id']}/games/letter-detective/trials",
        json={
            "trial_number": 1,
            "stimulus": {"target": "b", "options": ["b", "d", "p"]},
            "expected_response": "b",
            "game_version": "1.0.0",
            "domain": "visual-symbol-discrimination",
            "difficulty": 2,
            "correctness": True,
            "reaction_time_ms": 800,
            "completed_at": "2026-01-01T12:00:05.000Z",
        },
    ).json()
    return {"child": child.json(), "assessment": assessment, "trial": trial}


def _batch(samples: list | None = None, fixations: list | None = None, **overrides) -> dict:
    payload = {
        "provider": "webgazer",
        "provider_version": "1.0",
        "samples": samples
        or [{"x": 120.0, "y": 84.0, "timestamp_ms": 1000.0, "viewport_width": 1280, "viewport_height": 720}],
        "fixations": fixations or [],
    }
    payload.update(overrides)
    return payload


def test_a_gaze_status_communicates_boundary(client: TestClient) -> None:
    response = client.get("/api/gaze/status")
    assert response.status_code == 200
    body = response.json()
    assert body["modality"] == "gaze"
    assert body["raw_media_stored"] is False
    assert body["sample_schema_version"] == "1.0"


def test_b_valid_batch_creates_samples_and_fixations(client: TestClient) -> None:
    data = _setup(client)
    fixations = [{"start_timestamp_ms": 1000.0, "end_timestamp_ms": 1180.0, "duration_ms": 180, "x": 120.0, "y": 84.0, "target_type": "target"}]
    response = client.post(f"/api/gaze/trials/{data['trial']['id']}/gaze", json=_batch(fixations=fixations))
    assert response.status_code == 201
    body = response.json()
    assert body["samples_created"] == 1
    assert body["fixations_created"] == 1
    assert body["samples_rejected"] == 0
    summary = client.get(f"/api/gaze/trials/{data['trial']['id']}/gaze").json()
    assert summary["sample_count"] == 1
    assert summary["fixation_count"] == 1
    assert summary["fixations"][0]["target_type"] == "target"


def test_c_invalid_coordinates_are_rejected(client: TestClient) -> None:
    data = _setup(client)
    payload = _batch(
        samples=[
            {"x": -5.0, "y": 10.0, "timestamp_ms": 2.0},
            {"x": 5000.0, "y": 10.0, "timestamp_ms": 3.0, "viewport_width": 1280, "viewport_height": 720},
            {"x": 50.0, "y": 50.0, "timestamp_ms": 4.0, "viewport_width": 1280, "viewport_height": 720},
        ]
    )
    response = client.post(f"/api/gaze/trials/{data['trial']['id']}/gaze", json=payload)
    body = response.json()
    assert body["samples_created"] == 1
    assert body["samples_rejected"] == 2
    assert body["quality"] == "degraded"


def test_d_out_of_viewport_samples_are_rejected(client: TestClient) -> None:
    data = _setup(client)
    payload = _batch(samples=[{"x": 5000.0, "y": 50.0, "timestamp_ms": 1.0, "viewport_width": 1280, "viewport_height": 720}])
    response = client.post(f"/api/gaze/trials/{data['trial']['id']}/gaze", json=payload)
    assert response.json()["samples_rejected"] == 1


def test_e_out_of_order_timestamps_mark_quality_degraded(client: TestClient) -> None:
    data = _setup(client)
    payload = _batch(
        samples=[
            {"x": 100.0, "y": 100.0, "timestamp_ms": 300.0},
            {"x": 110.0, "y": 105.0, "timestamp_ms": 200.0},
        ]
    )
    response = client.post(f"/api/gaze/trials/{data['trial']['id']}/gaze", json=payload)
    body = response.json()
    assert body["samples_created"] == 2
    assert body["quality"] == "degraded"
    summary = client.get(f"/api/gaze/trials/{data['trial']['id']}/gaze").json()
    assert summary["quality"] == "degraded"


def test_f_unknown_trial_returns_404(client: TestClient) -> None:
    response = client.post(f"/api/gaze/trials/00000000-0000-0000-0000-000000000000/gaze", json=_batch())
    assert response.status_code == 404


def test_g_behavior_features_survive_without_gaze(client: TestClient) -> None:
    from app.ml.features import extract_session_features
    from app.ml.validation import validate_trials

    class _Trial:
        id = "t1"
        completed_at = True
        correctness = True
        reaction_time_ms = 800
        hesitation_time_ms = 100
        error_count = 0
        score = 1
        started_at = 1
        domain = "accuracy"

    trials = [_Trial()]
    features, quality = extract_session_features(None, [], trials, [])
    assert features["overall_accuracy"]["value"] == 1.0
    assert features["gaze_available"]["available"] is False
    assert features["gaze_fixation_count"]["value"] is None
    assert quality["available_feature_count"] >= 0


def test_h_insufficient_samples_yield_missing_not_zero(client: TestClient) -> None:
    result = analyze_fixations(0, [])
    assert result["gaze_fixation_count"] == 0
    assert result["gaze_mean_fixation_duration_ms"] is None
    assert result["gaze_scanpath_entropy"] is None
    assert result["gaze_horizontal_saccade_bias"] is None


def test_i_extraction_is_deterministic(client: TestClient) -> None:
    fixations = [
        {"start_epoch_ms": 0.0, "end_epoch_ms": 200.0, "duration_ms": 200, "x": 100.0, "y": 100.0, "target_type": "target"},
        {"start_epoch_ms": 400.0, "end_epoch_ms": 560.0, "duration_ms": 160, "x": 220.0, "y": 100.0, "target_type": "option"},
        {"start_epoch_ms": 700.0, "end_epoch_ms": 900.0, "duration_ms": 200, "x": 120.0, "y": 100.0, "target_type": "target"},
    ]
    first = analyze_fixations(10, fixations)
    second = analyze_fixations(10, [dict(item) for item in fixations])
    assert first == second


def test_j_target_and_distractor_fixation_times(client: TestClient) -> None:
    fixations = [
        {"start_epoch_ms": 0.0, "end_epoch_ms": 200.0, "duration_ms": 200, "x": 100.0, "y": 100.0, "target_type": "target"},
        {"start_epoch_ms": 300.0, "end_epoch_ms": 500.0, "duration_ms": 200, "x": 300.0, "y": 100.0, "target_type": "option"},
        {"start_epoch_ms": 600.0, "end_epoch_ms": 700.0, "duration_ms": 100, "x": 100.0, "y": 100.0, "target_type": "target"},
    ]
    result = analyze_fixations(5, fixations)
    assert result["gaze_target_fixation_time_ms"] == 300
    assert result["gaze_distractor_fixation_time_ms"] == 200


def test_k_regression_count_is_directional(client: TestClient) -> None:
    fixations = [
        {"start_epoch_ms": 0.0, "end_epoch_ms": 200.0, "duration_ms": 200, "x": 100.0, "y": 100.0, "target_type": "target"},
        {"start_epoch_ms": 300.0, "end_epoch_ms": 480.0, "duration_ms": 180, "x": 260.0, "y": 100.0, "target_type": "option"},
        {"start_epoch_ms": 600.0, "end_epoch_ms": 800.0, "duration_ms": 200, "x": 120.0, "y": 100.0, "target_type": "target"},
    ]
    result = analyze_fixations(5, fixations)
    assert result["gaze_regression_count"] == 1


def test_l_fixation_switch_count(client: TestClient) -> None:
    fixations = [
        {"start_epoch_ms": 0.0, "end_epoch_ms": 200.0, "duration_ms": 200, "x": 100.0, "y": 100.0, "target_type": "target"},
        {"start_epoch_ms": 300.0, "end_epoch_ms": 480.0, "duration_ms": 180, "x": 260.0, "y": 100.0, "target_type": "option"},
        {"start_epoch_ms": 600.0, "end_epoch_ms": 800.0, "duration_ms": 200, "x": 120.0, "y": 100.0, "target_type": "target"},
    ]
    assert analyze_fixations(5, fixations)["gaze_fixation_switch_count"] == 2


def test_m_scanpath_entropy_is_bounded_and_deterministic(client: TestClient) -> None:
    fixations = [
        {"start_epoch_ms": 0.0, "end_epoch_ms": 200.0, "duration_ms": 200, "x": 100.0, "y": 100.0, "target_type": "target"},
        {"start_epoch_ms": 300.0, "end_epoch_ms": 480.0, "duration_ms": 180, "x": 260.0, "y": 100.0, "target_type": "option"},
        {"start_epoch_ms": 600.0, "end_epoch_ms": 800.0, "duration_ms": 200, "x": 120.0, "y": 100.0, "target_type": "target"},
        {"start_epoch_ms": 900.0, "end_epoch_ms": 1100.0, "duration_ms": 200, "x": 120.0, "y": 100.0, "target_type": "option"},
    ]
    entropy = analyze_fixations(5, fixations)["gaze_scanpath_entropy"]
    assert entropy == round(-((0.5) * __import__("math").log2(0.5) + (0.5) * __import__("math").log2(0.5)), 4)


def test_n_horizontal_bias_is_directional(client: TestClient) -> None:
    rightward = [
        {"start_epoch_ms": 0.0, "end_epoch_ms": 200.0, "duration_ms": 200, "x": 100.0, "y": 100.0, "target_type": "target"},
        {"start_epoch_ms": 300.0, "end_epoch_ms": 480.0, "duration_ms": 180, "x": 300.0, "y": 100.0, "target_type": "option"},
    ]
    assert analyze_fixations(5, rightward)["gaze_horizontal_saccade_bias"] == 1.0
    leftward = [
        {"start_epoch_ms": 0.0, "end_epoch_ms": 200.0, "duration_ms": 200, "x": 300.0, "y": 100.0, "target_type": "target"},
        {"start_epoch_ms": 300.0, "end_epoch_ms": 480.0, "duration_ms": 180, "x": 100.0, "y": 100.0, "target_type": "option"},
    ]
    assert analyze_fixations(5, leftward)["gaze_horizontal_saccade_bias"] == -1.0


def test_o_coverage_ratio_counts_observed_regions(client: TestClient) -> None:
    fixations = [
        {"start_epoch_ms": 0.0, "end_epoch_ms": 200.0, "duration_ms": 200, "x": 100.0, "y": 100.0, "target_type": "target"},
        {"start_epoch_ms": 300.0, "end_epoch_ms": 480.0, "duration_ms": 180, "x": 300.0, "y": 100.0, "target_type": "option"},
    ]
    result = analyze_fixations(5, fixations, region_labels=["target", "option", "instruction", "distractor"])
    assert result["gaze_coverage_ratio"] == round(0.5, 4)


def test_p_gaze_features_are_registered_with_modality(client: TestClient) -> None:
    for name in ("gaze_sample_count", "gaze_fixation_count", "gaze_mean_fixation_duration_ms", "gaze_target_fixation_time_ms", "gaze_scanpath_entropy", "gaze_horizontal_saccade_bias"):
        assert name in REGISTRY_BY_NAME
        assert REGISTRY_BY_NAME[name].modality == "gaze"


def test_q_no_raw_media_is_stored_or_transmitted(client: TestClient) -> None:
    data = _setup(client)
    payload = _batch(samples=[{"x": 10.0, "y": 10.0, "timestamp_ms": 1.0}], fixations=[{"start_timestamp_ms": 1.0, "end_timestamp_ms": 200.0, "duration_ms": 199, "x": 10.0, "y": 10.0}])
    response = client.post(f"/api/gaze/trials/{data['trial']['id']}/gaze", json=payload)
    assert response.status_code == 201
    summary = client.get(f"/api/gaze/trials/{data['trial']['id']}/gaze").json()
    serialized = str(summary).lower()
    for marker in ("data:image", "data:video", "videoframe", "base64"):
        assert marker not in serialized
    status_body = client.get("/api/gaze/status").json()
    assert status_body["raw_media_stored"] is False


def test_q2_aggregate_gaze_features_keep_missingness(client: TestClient) -> None:
    combined = aggregate_gaze_features([analyze_fixations(5, [{"start_epoch_ms": 0.0, "end_epoch_ms": 200.0, "duration_ms": 200, "x": 100.0, "y": 100.0, "target_type": "target"}])])
    assert combined["gaze_fixation_count"] == 1
    assert combined["gaze_scanpath_entropy"] is None
    assert aggregate_gaze_features([])["gaze_sample_count"] is None