"""Modality summary + calibration completion boundary tests."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _setup(client: TestClient, game_id: str = "letter-detective") -> dict:
    child = client.post("/api/children", json={"display_name": "Explorer", "birth_year": 2018})
    assessment = client.post("/api/assessments", json={"child_id": child.json()["id"], "version": "stage-2.0"}).json()
    trial = client.post(
        f"/api/assessments/{assessment['id']}/games/{game_id}/trials",
        json={
            "trial_number": 1,
            "stimulus": {"target": "b"},
            "expected_response": "b",
            "game_version": "1.0.0",
            "domain": "visual-symbol-discrimination",
            "difficulty": 1,
            "correctness": True,
            "reaction_time_ms": 700,
            "completed_at": "2026-01-01T12:00:05.000Z",
        },
    ).json()
    return {"child": child.json(), "assessment": assessment, "trial": trial}


def test_calibration_completed_event_is_created_when_flag_set(client: TestClient) -> None:
    setup = _setup(client)
    trial_id = setup["trial"]["id"]
    response = client.post(
        f"/api/gaze/trials/{trial_id}/gaze",
        json={
            "provider": "webgazer",
            "samples": [{"x": 100.0, "y": 90.0, "timestamp_ms": 100.0, "viewport_width": 1280, "viewport_height": 720}],
            "fixations": [],
            "calibration_completed": True,
        },
    )
    assert response.status_code == 201
    events = client.get(f"/api/trials/{trial_id}/events").json()
    assert any(event["event_type"] == "CALIBRATION_COMPLETED" for event in events)


def test_calibration_completed_event_is_deduplicated(client: TestClient) -> None:
    setup = _setup(client)
    trial_id = setup["trial"]["id"]
    payload = {
        "provider": "webgazer",
        "samples": [{"x": 100.0, "y": 90.0, "timestamp_ms": 100.0, "viewport_width": 1280, "viewport_height": 720}],
        "fixations": [],
        "calibration_completed": True,
    }
    client.post(f"/api/gaze/trials/{trial_id}/gaze", json=payload)
    client.post(f"/api/gaze/trials/{trial_id}/gaze", json=payload)
    events = client.get(f"/api/trials/{trial_id}/events").json()
    assert sum(1 for event in events if event["event_type"] == "CALIBRATION_COMPLETED") == 1


def test_calibration_flag_creates_no_event_when_false(client: TestClient) -> None:
    setup = _setup(client)
    trial_id = setup["trial"]["id"]
    client.post(
        f"/api/gaze/trials/{trial_id}/gaze",
        json={
            "provider": "webgazer",
            "samples": [{"x": 100.0, "y": 90.0, "timestamp_ms": 100.0, "viewport_width": 1280, "viewport_height": 720}],
            "fixations": [],
        },
    )
    events = client.get(f"/api/trials/{trial_id}/events").json()
    assert not any(event["event_type"] == "CALIBRATION_COMPLETED" for event in events)


def test_modality_summary_empty_when_nothing_recorded(client: TestClient) -> None:
    setup = _setup(client)
    body = client.get(f"/api/assessments/{setup['assessment']['id']}/modality-summary").json()
    assert body["assessment_id"] == setup["assessment"]["id"]
    assert body["gaze"]["recorded"] is False
    assert body["speech"]["recorded"] is False
    assert body["gaze"]["trial_coverage"] == 0.0
    assert body["speech"]["trial_coverage"] == 0.0


def test_modality_summary_reflects_gaze_and_speech(client: TestClient) -> None:
    setup = _setup(client)
    assessment_id = setup["assessment"]["id"]
    trial_id = setup["trial"]["id"]
    client.post(
        f"/api/gaze/trials/{trial_id}/gaze",
        json={
            "provider": "webgazer",
            "samples": [{"x": 110.0, "y": 80.0, "timestamp_ms": 100.0, "viewport_width": 1280, "viewport_height": 720}],
            "fixations": [{"start_timestamp_ms": 100.0, "end_timestamp_ms": 300.0, "duration_ms": 200, "x": 110.0, "y": 80.0, "target_type": "target"}],
            "calibration_completed": True,
        },
    )
    speech = client.post(
        "/api/speech/sessions",
        json={
            "session_id": assessment_id,
            "trial_id": trial_id,
            "task": {"task_id": "sound-quest:1:1", "expected_text": "cat", "language": "en", "difficulty": 1, "content_type": "word", "version": "3.0.0"},
            "language": "en",
            "provider": "webkit-speech-v1",
            "provider_version": "1.0",
            "audio_available": False,
        },
    )
    assert speech.status_code == 201
    speech_id = speech.json()["id"]
    client.post(
        f"/api/speech/sessions/{speech_id}/features",
        json={"features": {"speech_speech_detected": {"value": 1, "available": True}, "speech_transcript_similarity": {"value": 0.9, "available": True}}},
    )

    body = client.get(f"/api/assessments/{assessment_id}/modality-summary").json()
    assert body["gaze"]["recorded"] is True
    assert body["gaze"]["calibration_completed"] is True
    assert body["gaze"]["sample_count"] == 1
    assert body["gaze"]["fixation_count"] == 1
    assert body["gaze"]["trial_coverage"] == 1.0
    assert body["gaze"]["aoi_coverage"] == 1.0
    assert body["speech"]["recorded"] is True
    assert body["speech"]["trial_count"] == 1
    assert body["speech"]["trial_coverage"] == 1.0
    assert body["speech"]["transcript_available"] == 0
    assert body["speech"]["asr_available"] == 1