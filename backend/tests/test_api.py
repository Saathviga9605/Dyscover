import pytest
from fastapi.testclient import TestClient

from app.main import app



@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _create_assessment(client: TestClient, version: str = "stage-2.0") -> dict:
    child = client.post("/api/children", json={"display_name": "Explorer", "birth_year": 2018})
    assert child.status_code == 201
    assessment = client.post("/api/assessments", json={"child_id": child.json()["id"], "version": version})
    assert assessment.status_code == 201
    return assessment.json()


def _create_trial(client: TestClient, assessment_id: str, game_id: str, trial_number: int = 1, **overrides) -> dict:
    payload = {
        "trial_number": trial_number,
        "stimulus": {"target": "b", "options": ["b", "d"]},
        "expected_response": "b",
        "game_version": "1.0.0",
        "domain": "visual-symbol-discrimination",
        "difficulty": 2,
        "metadata": {"trial": trial_number},
        "correctness": True,
        "reaction_time_ms": 842,
        "completed_at": "2026-01-01T12:00:05.000Z",
        **overrides,
    }
    response = client.post(f"/api/assessments/{assessment_id}/games/{game_id}/trials", json=payload)
    assert response.status_code == 201
    return response.json()


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_child_assessment_contract(client: TestClient) -> None:
    child = client.post("/api/children", json={"display_name": "Explorer", "birth_year": 2018})
    assert child.status_code == 201
    child_id = child.json()["id"]
    assessment = client.post("/api/assessments", json={"child_id": child_id})
    assert assessment.status_code == 201
    assert assessment.json()["status"] == "planned"


def test_structured_trial_event_and_summary_contract(client: TestClient) -> None:
    child = client.post("/api/children", json={"display_name": "Explorer", "birth_year": 2018}).json()
    assessment = client.post("/api/assessments", json={"child_id": child["id"], "version": "stage-2.0"}).json()
    trial = client.post(f"/api/assessments/{assessment['id']}/games/letter-detective/trials", json={
        "trial_number": 1,
        "stimulus": {"target": "b", "options": ["b", "d"]},
        "expected_response": "b",
        "actual_response": "b",
        "game_version": "1.0.0",
        "domain": "visual-symbol-discrimination",
        "difficulty": 2,
        "correctness": True,
        "reaction_time_ms": 842,
        "metadata": {"distractorCount": 1},
    })
    assert trial.status_code == 201
    event = client.post(f"/api/trials/{trial.json()['id']}/events", json={
        "event_type": "RESPONSE_SUBMITTED",
        "session_id": assessment["id"],
        "game_id": "letter-detective",
        "sequence_number": 1,
        "performance_time": 842.5,
        "payload": {"optionId": "b", "isCorrect": True},
    })
    assert event.status_code == 201
    summary = client.post(f"/api/assessments/{assessment['id']}/summary", json={"games": [{"gameId": "letter-detective", "accuracy": 1}], "total_trials": 1})
    assert summary.status_code == 201
    assert summary.json()["schema_version"] == "2.0"


def test_ml_profile_extracts_and_persists_observed_features(client: TestClient) -> None:
    child = client.post("/api/children", json={"display_name": "Explorer", "birth_year": 2018}).json()
    assessment = client.post("/api/assessments", json={"child_id": child["id"], "version": "stage-3.0"}).json()
    profile = client.get(f"/api/ml/profile/session/{assessment['id']}")
    assert profile.status_code == 200
    assert profile.json()["mode"] == "OBSERVATION_ONLY"
    assert profile.json()["model"]["status"] == "unavailable"
    features = client.get(f"/api/ml/features/session/{assessment['id']}")
    assert features.status_code == 200
    assert features.json()["feature_schema_version"] == "1.0"


def test_ml_quality_has_explicit_governance_state(client: TestClient) -> None:
    quality = client.get("/api/ml/quality")
    assert quality.status_code == 200
    assert quality.json()["status"] in {"ok", "warning", "invalid"}
    assert "warnings" in quality.json()


def test_event_ingestion_persists_and_retrieves_event(client: TestClient) -> None:
    """A valid event must be accepted (NOT 422) and retrievable for its trial."""
    assessment = _create_assessment(client)
    trial = _create_trial(client, assessment["id"], "letter-detective")
    event = client.post(f"/api/trials/{trial['id']}/events", json={
        "event_type": "RESPONSE_SUBMITTED",
        "session_id": assessment["id"],
        "game_id": "letter-detective",
        "timestamp": "2026-01-01T12:00:04.000Z",
        "performance_time": 842.5,
        "sequence_number": 1,
        "schema_version": "2.0",
        "payload": {"optionId": "b", "isCorrect": True},
    })
    assert event.status_code == 201
    events = client.get(f"/api/trials/{trial['id']}/events")
    assert events.status_code == 200
    assert len(events.json()) == 1
    assert events.json()[0]["event_type"] == "RESPONSE_SUBMITTED"
    assert events.json()[0]["payload"] == {"optionId": "b", "isCorrect": True}


def test_event_requires_backend_trial_uuid(client: TestClient) -> None:
    """The exact regression: events posted to a locally generated (non-UUID) trial id must be rejected."""
    assessment = _create_assessment(client)
    _create_trial(client, assessment["id"], "letter-detective")
    response = client.post("/api/trials/letter-detective_trial_1_local/events", json={
        "event_type": "TRIAL_STARTED",
        "session_id": assessment["id"],
        "game_id": "letter-detective",
        "payload": {},
    })
    assert response.status_code == 422


def test_five_game_telemetry_paths_accepted(client: TestClient) -> None:
    """Every game can create a trial and submit a representative valid event."""
    representative = {
        "letter-detective": {"stimulus": {"target": "b", "options": ["b", "d"]}, "expected_response": "b", "domain": "visual-symbol-discrimination", "payload": {"optionId": "b"}},
        "mirror-match": {"stimulus": {"symbol": "P", "targetOrientation": "normal", "options": [{"id": "same", "label": "P", "orientation": "normal"}]}, "expected_response": "same", "domain": "visual-symbol-discrimination", "payload": {"optionId": "same"}},
        "word-flash": {"stimulus": {"word": "cat", "presentationMs": 1500, "options": ["cat", "bat"]}, "expected_response": "cat", "domain": "orthographic-recognition", "payload": {"optionId": "cat"}},
        "sequence-quest": {"stimulus": {"sequence": ["1", "2"], "displayMs": 2000}, "expected_response": ["1", "2"], "domain": "working-memory", "payload": {"submitted": ["1", "2"]}},
        "word-maze": {"stimulus": {"size": 3, "grid": [["c", "a", "t"], ["s", "u", "n"], ["d", "o", "g"]], "targets": ["cat", "sun"], "paths": {"cat": ["0,0", "0,1", "0,2"]}}, "expected_response": ["cat", "sun"], "domain": "attention-visual-search", "payload": {"found": ["cat"]}},
    }
    for game_id, spec in representative.items():
        assessment = _create_assessment(client)
        trial = _create_trial(client, assessment["id"], game_id, stimulus=spec["stimulus"], expected_response=spec["expected_response"], domain=spec["domain"])
        event = client.post(f"/api/trials/{trial['id']}/events", json={
            "event_type": "TRIAL_COMPLETED",
            "session_id": assessment["id"],
            "game_id": game_id,
            "sequence_number": 1,
            "performance_time": 842.5,
            "schema_version": "2.0",
            "payload": spec["payload"],
        })
        assert event.status_code == 201, f"{game_id} event rejected: {event.text}"


def test_end_to_end_telemetry_reaches_feature_extraction(client: TestClient) -> None:
    """Persisted trials and events must be visible to the existing feature extraction pipeline."""
    assessment = _create_assessment(client)
    trial = _create_trial(client, assessment["id"], "letter-detective", correctness=True, reaction_time_ms=842)
    event = client.post(f"/api/trials/{trial['id']}/events", json={
        "event_type": "SESSION_PAUSED",
        "session_id": assessment["id"],
        "game_id": "letter-detective",
        "sequence_number": 1,
        "performance_time": 1200.0,
        "schema_version": "2.0",
        "payload": {},
    })
    assert event.status_code == 201
    features = client.get(f"/api/ml/features/session/{assessment['id']}")
    assert features.status_code == 200
    body = features.json()
    assert body["features"]["pause_count"]["value"] == 1
    assert body["features"]["overall_accuracy"]["value"] == 1.0
    assert body["features"]["overall_accuracy"]["available"] is True
