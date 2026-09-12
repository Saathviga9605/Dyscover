"""Stage 7 — language-awareness tests (en + ta).

Covers the required surface:
- canonical l10n config (supported codes, locales, content version helpers)
- per-activity language availability (assessment + practice)
- language/locale/content_version metadata persisted and returned end-to-end
- backward compatibility: legacy English rows remain valid, defaults preserved
- speech locale derivation (ta -> ta-IN) and empty speech content honesty for
  languages without curated content
- remedial catalog / next-activity language filtering
- personalization recommendations never reference unavailable activities
- ML profile records language/locale as context (never a language-adjusted score)
"""

import pytest
from fastapi.testclient import TestClient

from app.l10n import (
    DEFAULT_LANGUAGE,
    L10N_CONTENT_VERSION,
    SUPPORTED_LANGUAGE_CODES,
    activities_for,
    is_activity_available,
    languages_for_activity,
    locale_for,
    resolve_language,
)
from app.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _create_child(client: TestClient, name: str = "Explorer") -> dict:
    response = client.post("/api/children", json={"display_name": name, "birth_year": 2018})
    assert response.status_code == 201
    return response.json()


def _create_assessment(client: TestClient, child_id: str, **overrides) -> dict:
    response = client.post("/api/assessments", json={"child_id": child_id, **overrides})
    assert response.status_code == 201
    return response.json()


def _create_trial(client: TestClient, assessment_id: str, game_id: str, trial_number: int = 1, domain: str = "visual-symbol-discrimination", correctness: bool = True) -> dict:
    payload = {
        "trial_number": trial_number,
        "stimulus": {"target": "b", "options": ["b", "d"]},
        "expected_response": "b",
        "game_version": "1.0.0",
        "domain": domain,
        "difficulty": 2,
        "correctness": correctness,
        "reaction_time_ms": 842,
        "completed_at": f"2026-01-01T12:00:{trial_number:02d}.000Z",
    }
    response = client.post(f"/api/assessments/{assessment_id}/games/{game_id}/trials", json=payload)
    assert response.status_code == 201
    return response.json()


# ---- canonical config ------------------------------------------------------

def test_supported_languages_and_locales() -> None:
    assert SUPPORTED_LANGUAGE_CODES == frozenset({"en", "ta"})
    assert locale_for("en") == "en-US"
    assert locale_for("ta") == "ta-IN"
    assert resolve_language(None) == DEFAULT_LANGUAGE
    assert resolve_language("ta") == "ta"
    assert resolve_language("fr") == DEFAULT_LANGUAGE
    assert locale_for("fr") == "en-US"


def test_activity_availability_classification() -> None:
    assert is_activity_available("letter-detective", "en") is True
    assert is_activity_available("letter-detective", "ta") is False
    assert is_activity_available("mirror-match", "en") is True
    assert is_activity_available("mirror-match", "ta") is True
    assert is_activity_available("word-flash", "ta") is False
    assert is_activity_available("sequence-quest", "ta") is False
    assert is_activity_available("word-maze", "ta") is False
    assert is_activity_available("no-such-activity", "en") is False


def test_languages_per_activity() -> None:
    assert languages_for_activity("mirror-match") == frozenset({"en", "ta"})
    assert languages_for_activity("letter-detective") == frozenset({"en"})
    assert activities_for("en") == frozenset(
        {
            "letter-detective", "mirror-match", "word-flash", "sequence-quest", "word-maze",
            "sound-quest-adventure", "letter-bubble-pop", "maze-runner-rush",
            "symbol-match", "word-builder", "sequence-recall", "visual-search",
            "sound-quest", "letter-pop", "maze-ran",
        }
    )
    assert activities_for("ta") == frozenset({"mirror-match", "symbol-match"})


def test_unknown_language_falls_back_to_english_for_availability() -> None:
    assert is_activity_available("letter-detective", "fr") is True
    assert activities_for("fr") == activities_for(DEFAULT_LANGUAGE)


# ---- assessment metadata + modality summary -------------------------------

def test_assessment_language_metadata_round_trip(client: TestClient) -> None:
    child = _create_child(client)
    assessment = _create_assessment(client, child["id"], language="ta")
    assert assessment["language"] == "ta"
    assert assessment["locale"] == "ta-IN"
    assert assessment["content_version"] == L10N_CONTENT_VERSION


def test_modality_summary_carries_language_context(client: TestClient) -> None:
    child = _create_child(client)
    assessment = _create_assessment(client, child["id"], language="ta")
    _create_trial(client, assessment["id"], "mirror-match", trial_number=1)
    response = client.post(
        f"/api/assessments/{assessment['id']}/summary",
        json={"games": [], "total_trials": 1},
    )
    assert response.status_code == 201
    summary = client.get(f"/api/assessments/{assessment['id']}/modality-summary")
    assert summary.status_code == 200
    body = summary.json()
    assert body["language"] == "ta"
    assert body["locale"] == "ta-IN"
    assert body["content_version"] == L10N_CONTENT_VERSION


def test_legacy_assessment_defaults_to_english(client: TestClient) -> None:
    child = _create_child(client)
    assessment = _create_assessment(client, child["id"])
    assert assessment["language"] == DEFAULT_LANGUAGE
    assert assessment["locale"] == "en-US"
    assert assessment["content_version"] == L10N_CONTENT_VERSION


# ---- speech locale ----------------------------------------------------------

def test_speech_session_derives_tamil_locale(client: TestClient) -> None:
    child = _create_child(client, "Reader")
    assessment = _create_assessment(client, child["id"])
    response = client.post(
        "/api/speech/sessions",
        json={"session_id": assessment["id"], "task": {"task_id": "fixture", "expected_text": "nai"}, "language": "ta"},
    )
    assert response.status_code == 201
    assert response.json()["locale"] == "ta-IN"
    fetched = client.get(f"/api/speech/sessions/{response.json()['id']}")
    assert fetched.json()["locale"] == "ta-IN"


def test_speech_session_default_locale_is_en_us(client: TestClient) -> None:
    child = _create_child(client, "Reader")
    assessment = _create_assessment(client, child["id"])
    response = client.post(
        "/api/speech/sessions",
        json={"session_id": assessment["id"], "task": {"task_id": "fixture", "expected_text": "the cat sat"}},
    )
    assert response.status_code == 201
    assert response.json()["locale"] == "en-US"


# ---- remedial language gating ---------------------------------------------

def test_remedial_catalog_lists_languages_per_activity(client: TestClient) -> None:
    response = client.get("/api/remedial/activities")
    assert response.status_code == 200
    by_id = {item["activity_id"]: item for item in response.json()}
    assert by_id["symbol-match"]["languages"] == ["en", "ta"]
    assert by_id["word-builder"]["languages"] == ["en"]


def test_remedial_catalog_filters_by_language(client: TestClient) -> None:
    response = client.get("/api/remedial/activities?language=ta")
    assert response.status_code == 200
    by_id = {item["activity_id"]: item for item in response.json()}
    assert set(by_id) == {"symbol-match"}


def test_speech_tasks_are_empty_for_tamil(client: TestClient) -> None:
    response = client.get("/api/remedial/activities/sound-quest/speech-tasks?language=ta")
    assert response.status_code == 404
    assert "No curated speech content" in response.json()["detail"]


def test_speech_tasks_search_game_available_in_english(client: TestClient) -> None:
    response = client.get("/api/remedial/activities/sound-quest/speech-tasks?language=en&count=2")
    assert response.status_code == 200
    assert response.json()["language"] == "en"


def test_practice_session_rejects_ta_activity_without_curated_content(client: TestClient) -> None:
    child = _create_child(client)
    response = client.post(
        "/api/remedial/sessions",
        json={"child_id": child["id"], "activity_id": "word-builder", "difficulty": 2, "language": "ta"},
    )
    assert response.status_code == 409


def test_practice_session_allows_symbol_match_in_tamil(client: TestClient) -> None:
    child = _create_child(client)
    response = client.post(
        "/api/remedial/sessions",
        json={"child_id": child["id"], "activity_id": "symbol-match", "difficulty": 2, "language": "ta"},
    )
    assert response.status_code == 201
    assert response.json()["language"] == "ta"
    assert response.json()["content_version"] == L10N_CONTENT_VERSION


def test_practice_session_defaults_to_english(client: TestClient) -> None:
    child = _create_child(client)
    response = client.post(
        "/api/remedial/sessions",
        json={"child_id": child["id"], "activity_id": "symbol-match", "difficulty": 2},
    )
    assert response.status_code == 201
    assert response.json()["language"] == "en"


def test_next_activity_respects_language(client: TestClient) -> None:
    child = _create_child(client)
    response = client.get(f"/api/remedial/children/{child['id']}/next-activity?language=ta")
    assert response.status_code == 200
    recommendation = response.json()
    assert recommendation["language"] == "ta"
    assert recommendation["activity"]["activity_id"] == "symbol-match"


# ---- personalization gating -----------------------------------------------

def test_personalization_recommendations_filtered_to_tamil(client: TestClient) -> None:
    child = _create_child(client)
    assessment = _create_assessment(client, child["id"], language="ta")
    for i in range(3):
        _create_trial(client, assessment["id"], "mirror-match", trial_number=i + 1)
    client.post(f"/api/assessments/{assessment['id']}/summary", json={"games": [], "total_trials": 3})
    response = client.get(f"/api/personalization/children/{child['id']}/recommendations?language=ta")
    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "ta"
    for item in body["recommendations"]:
        if item["game_id"] is not None:
            assert is_activity_available(item["game_id"], "ta") is True


# ---- ML context -----------------------------------------------------------

def test_ml_profile_records_language_as_context(client: TestClient) -> None:
    child = _create_child(client)
    assessment = _create_assessment(client, child["id"], language="ta")
    _create_trial(client, assessment["id"], "mirror-match", trial_number=1)
    client.post(f"/api/assessments/{assessment['id']}/summary", json={"games": [], "total_trials": 1})
    profile = client.get(f"/api/ml/profile/session/{assessment['id']}")
    assert profile.status_code == 200
    body = profile.json()
    assert body["language"] == "ta"
    assert body["locale"] == "ta-IN"
    assert body["mode"] == "OBSERVATION_ONLY"
    assert body["model"]["mode"] == "UNAVAILABLE"


def test_ml_profile_stays_english_by_default(client: TestClient) -> None:
    child = _create_child(client)
    assessment = _create_assessment(client, child["id"])
    _create_trial(client, assessment["id"], "letter-detective", trial_number=1)
    profile = client.get(f"/api/ml/profile/session/{assessment['id']}")
    assert profile.json()["language"] == "en"