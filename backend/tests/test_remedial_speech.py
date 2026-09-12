"""Speech restoration + parent-safety tests (R through X and AF through AJ).

Covers the legacy speech-game mapping (Sound Quest, Letter Bubble Pop, Maze
Runner Say It), deterministic speech-task content, backend speech session
capabability wiring, and the parent/dashboard safety boundaries.
"""

import re

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ml.profile import build_profile


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


PROHIBITED_WORDS = ("score", "diagnos", "treat", "improve", "at risk", "condition")


def _create_practice_opportunity(client: TestClient, n: int = 12) -> dict:
    child = client.post("/api/children", json={"display_name": "Explorer", "birth_year": 2018}).json()
    assessment = client.post("/api/assessments", json={"child_id": child["id"], "version": "stage-2.0"}).json()
    for index in range(n):
        client.post(
            f"/api/assessments/{assessment['id']}/games/word-flash/trials",
            json={
                "trial_number": index,
                "stimulus": {"word": "cat", "options": ["cat", "cap"]},
                "expected_response": "cat",
                "actual_response": "cat" if index % 2 == 0 else "cap",
                "game_version": "1.0.0",
                "domain": "phonological-awareness",
                "difficulty": 2,
                "correctness": index % 2 == 0,
                "score": 1 if index % 2 == 0 else 0,
                "error_count": 0 if index % 2 == 0 else 1,
                "reaction_time_ms": 900,
            },
        )
    return child


def test_r_legacy_speech_games_have_modern_activities(client: TestClient) -> None:
    activities = client.get("/api/remedial/activities").json()
    speech = {a["activity_id"]: a for a in activities if a["activity_type"] == "speech"}
    assert set(speech) == {"sound-quest", "letter-pop", "maze-ran"}
    # Mapping back to the legacy games: Sound Quest Adventure, Letter Bubble
    # Pop, Maze Runner Rush.
    assert speech["letter-pop"]["target_domain"] == "reading-fluency"
    assert speech["sound-quest"]["target_domain"] == "phonological-awareness"
    assert all(a["required_capabilities"] == ["microphone"] for a in speech.values())


def test_s_speech_task_content_is_deterministic(client: TestClient) -> None:
    first = client.get("/api/remedial/activities/sound-quest/speech-tasks?count=5&seed=3").json()
    second = client.get("/api/remedial/activities/sound-quest/speech-tasks?count=5&seed=3").json()
    assert first == second
    assert len(first["tasks"]) == 5
    task = first["tasks"][0]
    assert task["task_id"]
    assert task["expected_text"]
    assert task["language"] == "en"
    assert task["content_type"] == "word"
    assert first["content_version"]


def test_t_speech_activity_tasks_return_404_for_pointer_only(client: TestClient) -> None:
    response = client.get("/api/remedial/activities/symbol-match/speech-tasks")
    assert response.status_code == 404


def test_u_next_activity_excludes_microphone_by_default(client: TestClient) -> None:
    child = _create_practice_opportunity(client)
    recommendation = client.get(f"/api/remedial/children/{child['id']}/next-activity").json()
    assert recommendation["activity"] is not None
    assert recommendation["activity"]["required_capabilities"] == ["pointer"]


def test_v_next_activity_can_target_microphone_capability(client: TestClient) -> None:
    child = _create_practice_opportunity(client)
    recommendation = client.get(f"/api/remedial/children/{child['id']}/next-activity?capabilities=microphone").json()
    assert recommendation["activity"]["required_capabilities"] == ["microphone"]


def test_w_speech_features_can_be_persisted_without_audio(client: TestClient) -> None:
    child = client.post("/api/children", json={"display_name": "Explorer", "birth_year": 2018}).json()
    assessment = client.post("/api/assessments", json={"child_id": child["id"], "version": "stage-2.0"}).json()
    session = client.post(
        "/api/speech/sessions",
        json={
            "session_id": assessment["id"],
            "task": {"task_id": "sound-quest-1-cat", "expected_text": "cat", "language": "en", "content_type": "word"},
            "language": "en",
            "provider": "web-speech-api",
            "provider_version": "1.0",
            "audio_available": False,
            "duration_ms": 3200,
        },
    ).json()
    stored = client.post(
        f"/api/speech/sessions/{session['id']}/features",
        json={"features": {"speech_reading_duration_ms": {"value": 3200, "available": True, "modality": "speech"}}},
    )
    assert stored.status_code == 200
    retrieved = client.get(f"/api/speech/sessions/{session['id']}/features").json()
    assert retrieved["speech_available"] is True
    assert retrieved["features"]["speech_reading_duration_ms"]["value"] == 3200


def test_x_practice_sessions_support_speech_activities(client: TestClient) -> None:
    child = client.post("/api/children", json={"display_name": "Explorer", "birth_year": 2018}).json()
    created = client.post("/api/remedial/sessions", json={"child_id": child["id"], "activity_id": "sound-quest"})
    assert created.status_code == 201
    body = created.json()
    assert body["activity_id"] == "sound-quest"
    assert body["target_domain"] == "phonological-awareness"
    started = client.post(f"/api/remedial/sessions/{body['id']}/start")
    assert started.status_code == 200
    event = client.post(
        f"/api/remedial/sessions/{body['id']}/events",
        json={"event_type": "RESPONSE_SUBMITTED", "payload": {"transcript": "cat", "duration_ms": 3200}},
    )
    assert event.status_code == 201
    assert client.post(f"/api/remedial/sessions/{body['id']}/complete").status_code == 200


def test_af_profile_observations_never_use_clinical_language(client: TestClient) -> None:
    from app.ml.features import extract_session_features

    features, _ = extract_session_features(None, [], [], [], gaze_features={"gaze_sample_count": 5}, speech_sessions=[{"features": {"speech_reading_duration_ms": {"value": 3000, "available": True, "modality": "speech"}}}])
    profile = build_profile("s", features, {"trial_count": 0, "feature_schema_version": "1.0"})
    lowered = " ".join(profile["observations"]).lower()
    for word in PROHIBITED_WORDS:
        assert word not in lowered


def test_ag_profile_never_exposes_raw_gaze_analytics(client: TestClient) -> None:
    from app.ml.features import extract_session_features

    features, _ = extract_session_features(None, [], [], [], gaze_features={"gaze_sample_count": 100, "gaze_fixation_count": 7})
    profile = build_profile("s", features, {"trial_count": 0, "feature_schema_version": "1.0"})
    serialized = str(profile)
    assert "gaze_sample_count" not in serialized
    assert "gaze_fixation_count" not in serialized
    assert "available_modalities" in profile


def test_ah_no_gaze_means_no_gaze_copy(client: TestClient) -> None:
    from app.ml.features import extract_session_features

    features, _ = extract_session_features(None, [], [], [])
    profile = build_profile("s", features, {"trial_count": 0, "feature_schema_version": "1.0"})
    assert "gaze" not in profile["available_modalities"]
    assert not any("eye-movement" in item.lower() for item in profile["observations"])


def test_ai_unavailable_speech_yields_neutral_observation(client: TestClient) -> None:
    from app.ml.features import extract_session_features

    features, _ = extract_session_features(None, [], [], [], speech_sessions=[{"features": {"speech_reading_duration_ms": {"value": None, "available": False}}}])
    profile = build_profile("s", features, {"trial_count": 0, "feature_schema_version": "1.0"})
    text = " ".join(profile["observations"]).lower()
    assert "no recognized speech" in text
    for word in PROHIBITED_WORDS:
        assert word not in text


def test_aj_practice_copy_is_parent_safe_for_speech(client: TestClient) -> None:
    activities = client.get("/api/remedial/activities").json()
    for activity in activities:
        if activity["activity_type"] != "speech":
            continue
        lowered = f"{activity['display_name']} {activity['description']}".lower()
        for word in PROHIBITED_WORDS:
            assert word not in lowered
        assert re.search(r"read|say|speak|word|letter|microphone", lowered)