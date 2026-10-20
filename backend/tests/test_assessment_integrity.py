"""Trial scoring, idempotency and state-transition integrity."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.assessments.scoring import KNOWN_GAMES, score_trial
from tests.helpers import outcome, trial_payload


def _assessment(client: TestClient) -> dict:
    child = client.post("/api/children", json={"display_name": "Explorer"}).json()
    return client.post("/api/assessments", json={"child_id": child["id"]}).json()


# Parity with frontend/src/games/definitions/*.ts evaluateResponse.
@pytest.mark.parametrize(
    "game,stimulus,expected,actual,correct,score",
    [
        ("letter-detective", {}, "b", "B", True, 1.0),
        ("letter-detective", {}, "b", "d", False, 0.0),
        ("letter-detective", {}, "b", None, False, 0.0),
        ("word-flash", {}, "cat", "cat", True, 1.0),
        ("word-flash", {}, "cat", "Cat", False, 0.0),
        ("mirror-match", outcome("mirror-match", True)["stimulus"], "option-0", "option-0", True, 1.0),
        ("mirror-match", outcome("mirror-match", True)["stimulus"], "option-0", "option-1", False, 0.0),
        ("mirror-match", outcome("mirror-match", True)["stimulus"], "option-0", "missing", False, 0.0),
        ("sequence-quest", {}, ["a", "b", "c"], ["a", "b", "c"], True, 1.0),
        ("sequence-quest", {}, ["a", "b", "c"], ["a", "c", "b"], False, 1 / 3),
        ("sequence-quest", {}, ["a", "b", "c"], "abc", False, 0.0),
        ("word-maze", {}, ["cat", "sun"], ["cat", "sun"], True, 1.0),
        ("word-maze", {}, ["cat", "sun"], ["cat"], False, 0.5),
        ("word-maze", {}, ["cat", "sun"], ["cat", "cat", "zzz"], False, 0.5),
    ],
)
def test_server_scoring_matches_game_rules(game, stimulus, expected, actual, correct, score) -> None:
    result = score_trial(game, stimulus, expected, actual)
    assert result.correct is correct
    assert result.score == pytest.approx(score)


def test_speech_games_are_client_scored() -> None:
    for game in ("sound-quest-adventure", "letter-bubble-pop", "maze-runner-rush"):
        assert game in KNOWN_GAMES and score_trial(game, {}, "cat", "cat") is None


def test_fabricated_correct_result_is_rescored(client: TestClient) -> None:
    assessment = _assessment(client)
    payload = trial_payload("letter-detective", 1, False)
    payload.update({"correctness": True, "score": 1})  # client lies
    trial = client.post(f"/api/assessments/{assessment['id']}/games/letter-detective/trials", json=payload)
    assert trial.status_code == 201
    body = trial.json()
    assert body["correctness"] is False and body["score"] == 0
    assert body["metadata"]["scoring"] == "server_verified"
    assert body["metadata"]["client_reported"] == {"correctness": True, "score": 1.0}


def test_malformed_trials_are_rejected(client: TestClient) -> None:
    assessment = _assessment(client)
    base = f"/api/assessments/{assessment['id']}/games"
    assert client.post(f"{base}/sequence-quest/trials", json=trial_payload("sequence-quest", 1, True, expected_response="not-a-list")).status_code == 422
    assert client.post(f"{base}/unknown-game/trials", json=trial_payload("letter-detective", 1, True)).status_code == 422
    assert client.post(f"{base}/letter-detective/trials", json=trial_payload("letter-detective", 1, True, domain="made-up")).status_code == 422
    assert client.post(f"{base}/letter-detective/trials", json=trial_payload("letter-detective", 1, True, score=7)).status_code == 422
    assert client.post(f"{base}/letter-detective/trials", json=trial_payload("letter-detective", 1, True, reaction_time_ms=-1)).status_code == 422


def test_trial_and_event_writes_are_idempotent(client: TestClient) -> None:
    assessment = _assessment(client)
    path = f"/api/assessments/{assessment['id']}/games/word-flash/trials"
    first = client.post(path, json=trial_payload("word-flash", 1, True))
    retry = client.post(path, json=trial_payload("word-flash", 1, True))
    assert first.status_code == 201 and retry.status_code == 200
    assert first.json()["id"] == retry.json()["id"]

    event = {"event_type": "RESPONSE_SUBMITTED", "sequence_number": 3, "payload": {"x": 1}}
    one = client.post(f"/api/trials/{first.json()['id']}/events", json=event)
    two = client.post(f"/api/trials/{first.json()['id']}/events", json=event)
    assert one.status_code == 201 and two.status_code == 200 and one.json()["id"] == two.json()["id"]
    assert len(client.get(f"/api/trials/{first.json()['id']}/events").json()) == 1


def test_event_session_id_is_bound_to_trial_assessment(client: TestClient) -> None:
    assessment, other = _assessment(client), _assessment(client)
    trial = client.post(f"/api/assessments/{assessment['id']}/games/word-flash/trials", json=trial_payload("word-flash", 1, True)).json()
    event = client.post(f"/api/trials/{trial['id']}/events", json={"event_type": "TRIAL_STARTED", "session_id": other["id"]})
    assert event.json()["session_id"] == assessment["id"]


def test_calibration_event_cannot_be_forged_by_clients(client: TestClient) -> None:
    assessment = _assessment(client)
    trial = client.post(f"/api/assessments/{assessment['id']}/games/word-flash/trials", json=trial_payload("word-flash", 1, True)).json()
    assert client.post(f"/api/trials/{trial['id']}/events", json={"event_type": "CALIBRATION_COMPLETED"}).status_code == 422


def test_assessment_lifecycle_and_completed_sessions_are_closed(client: TestClient) -> None:
    assessment = _assessment(client)
    assert assessment["status"] == "planned"
    path = f"/api/assessments/{assessment['id']}/games/letter-detective/trials"
    client.post(path, json=trial_payload("letter-detective", 1, True))
    assert client.get(f"/api/assessments/{assessment['id']}").json()["status"] == "in_progress"
    summary = client.post(f"/api/assessments/{assessment['id']}/summary", json={"games": [], "total_trials": 999})
    assert summary.status_code == 201
    assert summary.json()["total_trials"] == 1  # counted server-side, not trusted
    completed = client.get(f"/api/assessments/{assessment['id']}").json()
    assert completed["status"] == "completed" and completed["completed_at"]
    assert client.post(path, json=trial_payload("letter-detective", 2, True)).status_code == 409


def test_assessment_history_is_paginated(client: TestClient) -> None:
    child = client.post("/api/children", json={"display_name": "Explorer"}).json()
    for _ in range(3):
        client.post("/api/assessments", json={"child_id": child["id"]})
    page = client.get(f"/api/children/{child['id']}/assessments?limit=2").json()
    rest = client.get(f"/api/children/{child['id']}/assessments?limit=2&offset=2").json()
    assert len(page) == 2 and len(rest) == 1
    assert client.get(f"/api/children/{child['id']}/assessments?limit=0").status_code == 422


def test_unsupported_language_is_rejected(client: TestClient) -> None:
    child = client.post("/api/children", json={"display_name": "Explorer"}).json()
    assert client.post("/api/assessments", json={"child_id": child["id"], "language": "fr"}).status_code == 422
    tamil = client.post("/api/assessments", json={"child_id": child["id"], "language": "ta"}).json()
    assert tamil["locale"] == "ta-IN"


def test_gaze_batches_are_idempotent_and_missing_quality_is_unknown(client: TestClient) -> None:
    assessment = _assessment(client)
    trial = client.post(f"/api/assessments/{assessment['id']}/games/word-flash/trials", json=trial_payload("word-flash", 1, True)).json()
    empty = client.get(f"/api/gaze/trials/{trial['id']}/gaze").json()
    assert empty["sample_count"] == 0 and empty["quality"] is None
    batch = {"samples": [{"x": 10, "y": 10, "timestamp_ms": 1000}, {"x": 11, "y": 11, "timestamp_ms": 1016}], "fixations": []}
    assert client.post(f"/api/gaze/trials/{trial['id']}/gaze", json=batch).json()["samples_created"] == 2
    assert client.post(f"/api/gaze/trials/{trial['id']}/gaze", json=batch).json()["samples_created"] == 0
    assert client.get(f"/api/gaze/trials/{trial['id']}/gaze").json()["sample_count"] == 2


def test_modality_coverage_without_trials_is_null_not_zero(client: TestClient) -> None:
    summary = client.get(f"/api/assessments/{_assessment(client)['id']}/modality-summary").json()
    assert summary["gaze"]["trial_coverage"] is None
    assert summary["speech"]["trial_coverage"] is None
