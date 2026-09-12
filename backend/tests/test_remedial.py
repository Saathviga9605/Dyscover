"""Stage 6 remedial-learning tests (requirements A-R; S covered by the full
assessment suite, T by running every suite together).

These tests exercise the educational-practice machinery end-to-end through
the public API and assert the assessment/practice boundary explicitly.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

PROHIBITED_WORDS = (
    "dyslexia",
    "dyslexic",
    "disorder",
    "deficit",
    "severity",
    "diagnos",
    "probab",
    "risk",
    "impair",
    "treat",
    "improv",
)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _create_child(client: TestClient) -> dict:
    response = client.post("/api/children", json={"display_name": "Explorer", "birth_year": 2018})
    assert response.status_code == 201
    return response.json()


def _create_assessment(client: TestClient, child_id: str) -> dict:
    response = client.post("/api/assessments", json={"child_id": child_id})
    assert response.status_code == 201
    return response.json()


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


def _complete_assessment(client: TestClient, assessment_id: str, game_id: str, n: int, correctness: bool) -> None:
    for i in range(1, n + 1):
        _create_trial(client, assessment_id, game_id, trial_number=i, correctness=correctness, completed_at=f"2026-01-01T12:00:{5+i:02d}.000Z")
    response = client.post(f"/api/assessments/{assessment_id}/summary", json={"games": [], "total_trials": n})
    assert response.status_code == 201


def _create_practice(
    client: TestClient, child_id: str, activity_id: str = "symbol-match", events: int = 2
) -> tuple[dict, dict]:
    response = client.post(
        "/api/remedial/sessions",
        json={"child_id": child_id, "activity_id": activity_id, "difficulty": 2},
    )
    assert response.status_code == 201, response.text
    session = response.json()
    started = client.post(f"/api/remedial/sessions/{session['id']}/start")
    assert started.status_code == 200
    started_session = started.json()
    recorded = []
    for i in range(events):
        event = client.post(
            f"/api/remedial/sessions/{session['id']}/events",
            json={
                "event_type": "RESPONSE_SUBMITTED",
                "payload": {"stimulus": {"target": "b"}, "response": "b", "correct": i % 2 == 0, "difficulty": 2},
            },
        )
        assert event.status_code == 201
        recorded.append(event.json())
    return started_session, recorded


def _finish_practice(client: TestClient, session_id: str) -> dict:
    response = client.post(f"/api/remedial/sessions/{session_id}/complete")
    assert response.status_code == 200
    return response.json()


def _create_practice_opportunity_child(client: TestClient, game_id: str = "letter-detective", n: int = 4) -> dict:
    """Accuracy exactly at the practice threshold (0.5) => practice_opportunity."""
    child = _create_child(client)
    assessment = _create_assessment(client, child["id"])
    wrong = max(1, n // 2)
    for i in range(1, n + 1):
        _create_trial(
            client,
            assessment["id"],
            game_id,
            trial_number=i,
            correctness=i > wrong,
            completed_at=f"2026-01-01T12:00:{5+i:02d}.000Z",
        )
    client.post(f"/api/assessments/{assessment['id']}/summary", json={"games": [], "total_trials": n})
    return child


def test_a_catalog_is_wellformed_and_complete(client: TestClient) -> None:
    response = client.get("/api/remedial/activities")
    assert response.status_code == 200
    activities = response.json()
    assert len(activities) == 4
    assert {a["activity_id"] for a in activities} == {
        "symbol-match",
        "word-builder",
        "sequence-recall",
        "visual-search",
    }
    for activity in activities:
        assert activity["enabled"] is True
        assert activity["activity_type"] == "practice"
        assert activity["version"]
        assert activity["supporting_game"] in {
            "letter-detective",
            "word-flash",
            "sequence-quest",
            "word-maze",
        }
        assert activity["supported_difficulty_levels"] == [1, 2, 3, 4, 5]
        assert activity["age_range"] == [4, 10]
        assert activity["required_capabilities"] == ["pointer"]
        for word in PROHIBITED_WORDS:
            assert word not in activity["description"].lower()


def test_b_unknown_activity_is_rejected(client: TestClient) -> None:
    child = _create_child(client)
    response = client.post(
        "/api/remedial/sessions", json={"child_id": child["id"], "activity_id": "no-such-activity"}
    )
    assert response.status_code == 404


def test_c_practice_session_lifecycle_and_event_contract(client: TestClient) -> None:
    child = _create_child(client)
    created = client.post(
        "/api/remedial/sessions", json={"child_id": child["id"], "activity_id": "word-builder", "difficulty": 3}
    )
    assert created.status_code == 201
    session = created.json()
    assert session["status"] == "planned"
    assert session["mode"] == "practice"
    assert session["difficulty"] == 3

    started = client.post(f"/api/remedial/sessions/{session['id']}/start")
    assert started.status_code == 200
    assert started.json()["status"] == "active"
    assert started.json()["started_at"] is not None

    stimulus = client.post(
        f"/api/remedial/sessions/{session['id']}/events",
        json={"event_type": "STIMULUS_SHOWN", "payload": {"stimulus": {"word": "cat"}, "difficulty": 3}},
    )
    assert stimulus.status_code == 201
    event = stimulus.json()
    for field in ("id", "practice_session_id", "mode", "event_type", "timestamp", "sequence_number", "schema_version", "payload"):
        assert field in event
    assert event["mode"] == "practice"
    assert event["schema_version"] == "2.0"
    assert event["sequence_number"] == 1

    response = client.post(
        f"/api/remedial/sessions/{session['id']}/events",
        json={"event_type": "RESPONSE_SUBMITTED", "payload": {"correct": True, "difficulty": 3}},
    )
    assert response.json()["sequence_number"] == 2

    completed = client.post(f"/api/remedial/sessions/{session['id']}/complete")
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["completed_at"] is not None

    # Terminal states are final.
    again = client.post(f"/api/remedial/sessions/{session['id']}/complete")
    assert again.status_code == 409


def test_d_practice_events_follow_canonical_contract(client: TestClient) -> None:
    child = _create_child(client)
    _, events = _create_practice(client, child["id"], events=2)
    # SESSION_STARTED occupies sequence 0; each response follows in order.
    assert [e["sequence_number"] for e in events] == [1, 2]
    assert all(e["mode"] == "practice" for e in events)
    assert all(e["schema_version"] == "2.0" for e in events)


def test_e_practice_is_clearly_distinguishable_from_assessment(client: TestClient) -> None:
    child = _create_child(client)
    session, _ = _create_practice(client, child["id"])
    assert session["mode"] == "practice"

    assessment_list = client.get(f"/api/children/{child['id']}/assessments")
    assert assessment_list.status_code == 200
    assert assessment_list.json() == []

    progress = client.get(f"/api/remedial/children/{child['id']}/practice/progress")
    assert progress.status_code == 200
    assert progress.json()["totals"]["sessions_attempted"] >= 1


def test_f_practice_never_contaminates_assessment_evidence(client: TestClient) -> None:
    child = _create_practice_opportunity_child(client)
    before = client.get(f"/api/personalization/children/{child['id']}/profile").json()

    # A lot of practice telemetry, some 'wrong' answers.
    for _ in range(3):
        session, _ = _create_practice(client, child["id"])
        _finish_practice(client, session["id"])
    for _ in range(5):
        client.post(
            "/api/remedial/sessions",
            json={"child_id": child["id"], "activity_id": "symbol-match", "difficulty": 1},
        )

    after = client.get(f"/api/personalization/children/{child['id']}/profile").json()
    assert before == after


def test_g_evidence_backed_focused_selection(client: TestClient) -> None:
    child = _create_practice_opportunity_child(client)
    response = client.get(f"/api/remedial/children/{child['id']}/next-activity")
    assert response.status_code == 200
    recommendation = response.json()
    assert recommendation["kind"] == "focused"
    assert recommendation["target_domain"] == "visual-symbol-discrimination"
    assert recommendation["activity"]["activity_id"] == "symbol-match"


def test_h_insufficient_evidence_selects_neutral_balanced(client: TestClient) -> None:
    child = _create_child(client)
    response = client.get(f"/api/remedial/children/{child['id']}/next-activity")
    assert response.status_code == 200
    recommendation = response.json()
    assert recommendation["kind"] == "balanced"
    assert recommendation["activity"] is not None
    reason = (recommendation["reason"] or "").lower()
    for word in PROHIBITED_WORDS:
        assert word not in reason


def test_i_k_selection_is_deterministic(client: TestClient) -> None:
    child = _create_practice_opportunity_child(client)
    first = client.get(f"/api/remedial/children/{child['id']}/next-activity").json()
    second = client.get(f"/api/remedial/children/{child['id']}/next-activity").json()
    assert first == second


def test_j_l_difficulty_is_reused_from_stage5(client: TestClient) -> None:
    child = _create_practice_opportunity_child(client)
    activity = client.get("/api/remedial/activities").json()[0]
    game_id = activity["supporting_game"]
    stage5 = client.get(f"/api/personalization/children/{child['id']}/difficulty/{game_id}")
    assert stage5.status_code == 200
    recommendation = client.get(f"/api/remedial/children/{child['id']}/next-activity").json()
    assert recommendation["difficulty_level"] == stage5.json()["level"]


def test_m_difficulty_is_bounded_at_creation(client: TestClient) -> None:
    child = _create_child(client)
    high = client.post(
        "/api/remedial/sessions", json={"child_id": child["id"], "activity_id": "symbol-match", "difficulty": 99}
    )
    assert high.status_code == 201
    assert high.json()["difficulty"] == 5
    low = client.post(
        "/api/remedial/sessions", json={"child_id": child["id"], "activity_id": "symbol-match", "difficulty": -3}
    )
    assert low.status_code == 201
    assert low.json()["difficulty"] == 1


def test_n_invalid_telemetry_degrades_safely(client: TestClient) -> None:
    child = _create_child(client)
    session_response = client.post(
        "/api/remedial/sessions", json={"child_id": child["id"], "activity_id": "symbol-match", "difficulty": 1}
    )
    session = session_response.json()
    client.post(f"/api/remedial/sessions/{session['id']}/start")
    # Malformed correctness (not a boolean) should be ignored, not fatal.
    client.post(
        f"/api/remedial/sessions/{session['id']}/events",
        json={"event_type": "RESPONSE_SUBMITTED", "payload": {"correct": "yes"}},
    )
    client.post(
        f"/api/remedial/sessions/{session['id']}/events",
        json={"event_type": "RESPONSE_SUBMITTED", "payload": {"correct": True}},
    )
    _finish_practice(client, session["id"])

    progress = client.get(f"/api/remedial/children/{child['id']}/practice/progress")
    assert progress.status_code == 200
    data = progress.json()
    assert data["totals"]["sessions_completed"] == 1
    activity = [a for a in data["by_activity"] if a["activity_id"] == "symbol-match"][0]
    assert "first_accuracy_observed" not in activity
    assert "latest_accuracy_observed" not in activity


def test_o_child_facing_copy_contains_no_diagnostic_language(client: TestClient) -> None:
    texts: list[str] = []
    for activity in client.get("/api/remedial/activities").json():
        texts.append(activity["display_name"])
        texts.append(activity["description"])

    fresh = client.get(f"/api/remedial/children/{_create_child(client)['id']}/next-activity").json()
    texts.append(fresh["reason"])
    texts.append(fresh["activity"]["display_name"])

    focused_child = _create_practice_opportunity_child(client)
    focused = client.get(f"/api/remedial/children/{focused_child['id']}/next-activity").json()
    texts.append(focused["reason"])

    for text in texts:
        lowered = text.lower()
        for word in PROHIBITED_WORDS:
            assert word not in lowered, f"prohibited word '{word}' in: {text}"


def test_p_parent_oriented_progress_and_recommendation(client: TestClient) -> None:
    child = _create_practice_opportunity_child(client)
    session, recorded = _create_practice(client, child["id"], events=2)
    _finish_practice(client, session["id"])

    progress = client.get(f"/api/remedial/children/{child['id']}/practice/progress").json()
    assert progress["totals"]["sessions_completed"] == 1
    assert progress["note"]
    assert progress["totals"]["activities_available"] == 4
    assert progress["by_activity"]
    assert progress["recent_completed"]

    recommendation = client.get(f"/api/remedial/children/{child['id']}/next-activity").json()
    assert recommendation["reason"]
    lowered = recommendation["reason"].lower()
    for word in ("score", "diagnos", "treat", "improve"):
        assert word not in lowered


def test_q_progress_reports_observed_performance_with_valid_data(client: TestClient) -> None:
    child = _create_child(client)
    session_response = client.post(
        "/api/remedial/sessions", json={"child_id": child["id"], "activity_id": "word-builder", "difficulty": 2}
    )
    session = session_response.json()
    client.post(f"/api/remedial/sessions/{session['id']}/start")
    for correct in (True, True, False):
        client.post(
            f"/api/remedial/sessions/{session['id']}/events",
            json={"event_type": "RESPONSE_SUBMITTED", "payload": {"correct": correct, "difficulty": 2}},
        )
    _finish_practice(client, session["id"])

    data = client.get(f"/api/remedial/children/{child['id']}/practice/progress").json()
    assert data["totals"]["sessions_completed"] == 1
    activity = data["by_activity"][0]
    assert activity["activity_id"] == "word-builder"
    assert activity["accuracy_observed"] == pytest.approx(2 / 3, abs=0.01)
    assert "first_accuracy_observed" not in activity


def test_r_single_session_never_misleads_and_abandoned_is_not_completed(client: TestClient) -> None:
    child = _create_child(client)

    abandoned = client.post(
        "/api/remedial/sessions", json={"child_id": child["id"], "activity_id": "symbol-match", "difficulty": 1}
    ).json()
    client.post(f"/api/remedial/sessions/{abandoned['id']}/start")
    client.post(f"/api/remedial/sessions/{abandoned['id']}/abandon")

    completed = client.post(
        "/api/remedial/sessions", json={"child_id": child["id"], "activity_id": "sequence-recall", "difficulty": 1}
    ).json()
    client.post(f"/api/remedial/sessions/{completed['id']}/start")
    _finish_practice(client, completed["id"])

    data = client.get(f"/api/remedial/children/{child['id']}/practice/progress").json()
    assert data["totals"]["sessions_attempted"] == 2
    assert data["totals"]["sessions_completed"] == 1
    for activity in data["by_activity"]:
        if activity["completed"]:
            assert "first_accuracy_observed" not in activity
            assert "latest_accuracy_observed" not in activity


def test_s_assessment_telemetry_still_works_after_practice(client: TestClient) -> None:
    child = _create_practice_opportunity_child(client)
    session, _ = _create_practice(client, child["id"])
    _finish_practice(client, session["id"])

    assessment = _create_assessment(client, child["id"])
    trial = client.post(
        f"/api/assessments/{assessment['id']}/games/sequence-quest/trials",
        json={
            "trial_number": 1,
            "stimulus": {"sequence": ["a", "b"]},
            "expected_response": ["a", "b"],
            "game_version": "1.0.0",
            "domain": "working-memory",
            "difficulty": 1,
            "metadata": {},
            "correctness": True,
            "reaction_time_ms": 400,
            "completed_at": "2026-01-01T12:30:00.000Z",
        },
    )
    assert trial.status_code == 201