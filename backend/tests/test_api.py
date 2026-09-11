import pytest
from fastapi.testclient import TestClient

from app.main import app



@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


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
