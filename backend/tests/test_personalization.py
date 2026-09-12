"""Stage 5 — Deterministic Personalization Engine tests.

Covers the required test surface:
- A: no data handled safely
- B: insufficient trials -> insufficient_data
- C: sufficient observations -> sufficient_data + category
- D: relative category correctness (strength / practice / developing / mixed)
- E/F: difficulty moves modestly up (strong) and down (weak)
- G: difficulty stays within bounds (1..5)
- H: no oscillation / hysteresis on borderline windows
- J/K: recommendations with reasons; neutral when insufficient
- L: invalid data (negative timing, missing correctness) handled safely
- M: missing speech/gaze data still works (behavior-only)
- N: determinism (same data -> identical results)
- O: parent-safe language (no clinical/probability terms in output)
- P: progress / trends across multiple assessments
- Q: versioning / reproducibility (engine + schema + config summary)

Pure-logic tests operate on the deterministic functions directly; API tests
verify contracts through the FastAPI test client.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from app.main import app
from app.personalization.config import PERSONALIZATION_CONFIG
from app.personalization.skills import build_domain_skill, categorize
from app.personalization.difficulty import decide
from app.personalization.service import _utc_sort_key
from app.personalization import evidence


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


GAME_DOMAIN = {
    "letter-detective": "visual-symbol-discrimination",
    "mirror-match": "visual-symbol-discrimination",
    "word-flash": "orthographic-recognition",
    "sequence-quest": "working-memory",
    "word-maze": "attention-visual-search",
}

PROHIBITED_TERMS = (
    "risk",
    "diagnos",
    "disorder",
    "impairment",
    "disabled",
    "probability",
    "percentile",
    "clinical",
    "deficit",
    "delayed",
)


class _FakeTrial:
    def __init__(self, game_id, correctness=None, reaction_time_ms=None, completed_at="2026-01-01T12:00:00Z"):
        self.game_id = game_id
        self.correctness = correctness
        self.reaction_time_ms = reaction_time_ms
        self.completed_at = completed_at


def _fake_trials(game_id, outcomes, reaction_times=None):
    return [
        _FakeTrial(game_id, correct, None if reaction_times is None else (rt if correct else None))
        for correct, rt in zip(outcomes, reaction_times or [None] * len(outcomes))
    ]


def _collect_text(data: dict) -> list[str]:
    texts: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            texts.append(node)

    walk(data)
    return texts


def _assert_no_clinical_language(data: dict) -> None:
    lowered = " ".join(_collect_text(data)).lower()
    for term in PROHIBITED_TERMS:
        assert term not in lowered, f"prohibited clinical/suggestive term found: {term!r}"


# ---- A: no data ----------------------------------------------------------

def test_no_data_profile_and_neutral_recommendation(client: TestClient) -> None:
    child = client.post("/api/children", json={"display_name": "Explorer", "birth_year": 2018}).json()
    profile = client.get(f"/api/personalization/children/{child['id']}/profile")
    assert profile.status_code == 200
    assert profile.json()["skills"] == []

    recs = client.get(f"/api/personalization/children/{child['id']}/recommendations")
    assert recs.status_code == 200
    assert recs.json()["recommendations"][0]["kind"] == "neutral"
    assert recs.json()["recommendations"][0]["game_id"] is None


# ---- B: insufficient trials ---------------------------------------------

def test_insufficient_trials_are_insufficient(client: TestClient) -> None:
    child = client.post("/api/children", json={"display_name": "Explorer", "birth_year": 2018}).json()
    assessment = client.post("/api/assessments", json={"child_id": child["id"]}).json()
    for _ in range(1):
        client.post(
            f"/api/assessments/{assessment['id']}/games/letter-detective/trials",
            json={
                "trial_number": 1,
                "stimulus": {"target": "b", "options": ["b", "d"]},
                "expected_response": "b",
                "game_version": "1.0.0",
                "domain": "visual-symbol-discrimination",
                "difficulty": 2,
                "correctness": True,
                "completed_at": "2026-01-01T12:00:05.000Z",
            },
        )
    profile = client.get(f"/api/personalization/children/{child['id']}/profile")
    skill = next(s for s in profile.json()["skills"] if s["domain"] == "visual-symbol-discrimination")
    assert skill["evidence_state"] == "insufficient_data"
    assert skill["category"] == "insufficient_data"


# ---- C: sufficient observations -----------------------------------------

def test_sufficient_observations_yield_category(client: TestClient) -> None:
    trials = _fake_trials("letter-detective", [True, True, True, True])
    skill = build_domain_skill("visual-symbol-discrimination", trials, PERSONALIZATION_CONFIG)
    assert skill.evidence_state == "sufficient_data"
    assert skill.category == "relative_strength"


# ---- D: relative category mapping ---------------------------------------

@pytest.mark.parametrize(
    "outcomes,expected",
    [
        ([True, True, True, True, True], "relative_strength"),
        ([True, False, False, False, False], "practice_opportunity"),
        ([True, True, False, False, True], "developing"),
    ],
)
def test_category_by_accuracy(outcomes, expected) -> None:
    accuracy = sum(outcomes) / len(outcomes)
    category, _ = categorize(accuracy, PERSONALIZATION_CONFIG)
    assert category == expected


def test_category_matches_observed_only_and_never_clinical(client: TestClient) -> None:
    # Use the API path with a strong and a weak domain aggregated at child level.
    child = client.post("/api/children", json={"display_name": "Explorer", "birth_year": 2018}).json()
    assessment = client.post("/api/assessments", json={"child_id": child["id"]}).json()
    strong_game, weak_game = "letter-detective", "word-flash"
    for i in range(3):
        for game, correct in ((strong_game, True), (weak_game, False)):
            client.post(
                f"/api/assessments/{assessment['id']}/games/{game}/trials",
                json={
                    "trial_number": i + 1,
                    "stimulus": {"target": "b", "options": ["b", "d"]},
                    "expected_response": "b",
                    "game_version": "1.0.0",
                    "domain": GAME_DOMAIN[game],
                    "difficulty": 2,
                    "correctness": correct,
                    "completed_at": f"2026-01-01T12:00:{i + 1:02}.000Z",
                },
            )
    profile = client.get(f"/api/personalization/children/{child['id']}/profile")
    skills = {s["domain"]: s for s in profile.json()["skills"]}
    assert skills["visual-symbol-discrimination"]["category"] == "relative_strength"
    assert skills["orthographic-recognition"]["category"] == "practice_opportunity"
    _assert_no_clinical_language(profile.json())


# ---- E/F: difficulty up modestly / down modestly ------------------------

def test_difficulty_moves_up_by_one_on_strong_recent_window() -> None:
    rules = PERSONALIZATION_CONFIG.difficulty
    trials = _fake_trials("letter-detective", [True, True, True])
    decision = decide("letter-detective", trials, rules, current_level=1)
    assert decision.level == 2
    assert decision.changed is True
    assert decision.level - decision.previous_level == 1


def test_difficulty_moves_down_by_one_on_weak_recent_window() -> None:
    rules = PERSONALIZATION_CONFIG.difficulty
    trials = _fake_trials("letter-detective", [False, False, False, None])  # last ignored (no correctness)
    decision = decide("letter-detective", trials, rules, current_level=5)
    assert decision.level == 4
    assert decision.changed is True


# ---- G: difficulty stays within bounds -----------------------------------

def test_difficulty_never_exceeds_bounds() -> None:
    rules = PERSONALIZATION_CONFIG.difficulty
    at_max = decide("letter-detective", _fake_trials("letter-detective", [True, True, True]), rules, current_level=5)
    assert at_max.level == 5
    at_min = decide("letter-detective", _fake_trials("letter-detective", [False, False, False]), rules, current_level=1)
    assert at_min.level == 1


# ---- H: no oscillation / hysteresis --------------------------------------

def test_difficulty_holds_on_borderline_window() -> None:
    rules = PERSONALIZATION_CONFIG.difficulty
    # accuracy (0.67) sits between the decrease and increase thresholds
    # on the recent window, so the difficulty is held (no oscillation).
    trials = _fake_trials("letter-detective", [True, False, True, True])
    decision = decide("letter-detective", trials, rules, current_level=2)
    assert decision.level == 2
    assert decision.changed is False


# ---- J/K: recommendations -----------------------------------------------

def test_recommendation_has_reason_and_difficulty(client: TestClient) -> None:
    child = client.post("/api/children", json={"display_name": "Explorer", "birth_year": 2018}).json()
    assessment = client.post("/api/assessments", json={"child_id": child["id"]}).json()
    for i in range(3):
        client.post(
            f"/api/assessments/{assessment['id']}/games/word-flash/trials",
            json={
                "trial_number": i + 1,
                "stimulus": {"target": "cat", "options": ["cat", "bat"]},
                "expected_response": "cat",
                "game_version": "1.0.0",
                "domain": "orthographic-recognition",
                "difficulty": 2,
                "correctness": False,
                "completed_at": f"2026-01-01T12:00:{i + 1:02}.000Z",
            },
        )
    recs = client.get(f"/api/personalization/children/{child['id']}/recommendations")
    recommendations = recs.json()["recommendations"]
    assert recommendations, "expected a non-neutral recommendation"
    assert recommendations[0]["kind"] == "game_activity"
    assert recommendations[0]["reason"]
    assert recommendations[0]["game_id"] == "word-flash"
    assert 1 <= recommendations[0]["suggested_difficulty"] <= 5
    assert recommendations[0]["target_domain"] == "orthographic-recognition"
    assert recommendations[0]["target_domain_label"] == "Orthographic recognition"


def test_neutral_recommendation_no_clinical_language(client: TestClient) -> None:
    child = client.post("/api/children", json={"display_name": "Explorer", "birth_year": 2018}).json()
    recs = client.get(f"/api/personalization/children/{child['id']}/recommendations")
    assert recs.json()["recommendations"][0]["kind"] == "neutral"
    _assert_no_clinical_language(recs.json())


def test_recommendations_never_duplicate_a_domain_when_many_games_are_observed(client: TestClient) -> None:
    # letter-detective AND mirror-match both map to the same domain, so a
    # child observed playing both must not receive two visual-symbol entries.
    child = client.post("/api/children", json={"display_name": "Explorer", "birth_year": 2018}).json()
    assessment = client.post("/api/assessments", json={"child_id": child["id"]}).json()
    for game in ("letter-detective", "mirror-match"):
        for i in range(3):
            client.post(
                f"/api/assessments/{assessment['id']}/games/{game}/trials",
                json={
                    "trial_number": i + 1,
                    "stimulus": {"target": "b", "options": ["b", "d"]},
                    "expected_response": "b",
                    "game_version": "1.0.0",
                    "domain": GAME_DOMAIN[game],
                    "difficulty": 2,
                    "correctness": True,
                    "completed_at": f"2026-01-01T12:00:{i + 1:02}.000Z",
                },
            )
    recommendations = client.get(f"/api/personalization/children/{child['id']}/recommendations").json()["recommendations"]
    assert recommendations, "expected a non-neutral recommendation"
    domains = [rec["target_domain"] for rec in recommendations if rec["target_domain"] is not None]
    assert len(domains) == len(set(domains)), "a domain appears more than once"
    visual = [rec for rec in recommendations if rec["target_domain"] == "visual-symbol-discrimination"]
    assert len(visual) == 1
    assert visual[0]["game_id"] == "letter-detective"
    assert visual[0]["target_domain_label"] == "Visual symbol discrimination"


# ---- L: invalid data handled safely --------------------------------------

def test_progress_sort_handles_mixed_naive_and_aware_timestamps() -> None:
    # Legacy persisted rows can mix offset-naive and offset-aware timestamps;
    # the assessment/trial sort keys must normalize before comparing.
    naive = datetime(2026, 1, 1, 12, 0, 0)
    aware = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
    keys = [_utc_sort_key(aware), _utc_sort_key(naive)]
    assert sorted(keys) == [_utc_sort_key(naive), _utc_sort_key(aware)]
    assert _utc_sort_key(None) == datetime.min.replace(tzinfo=timezone.utc)
    assert _utc_sort_key(aware) == aware.astimezone(timezone.utc)
    assert _utc_sort_key(naive) == naive.replace(tzinfo=timezone.utc)


def test_invalid_timing_does_not_taint_aggregates() -> None:
    trials = [_FakeTrial("letter-detective", True, 800), _FakeTrial("letter-detective", True, -500), _FakeTrial("letter-detective", True, 900), _FakeTrial("letter-detective", True, 850)]
    skill = build_domain_skill("visual-symbol-discrimination", trials, PERSONALIZATION_CONFIG)
    assert skill.mean_reaction_time_ms is not None
    # negative RT excluded from timing aggregate
    assert skill.mean_reaction_time_ms == 850.0


def test_missing_correctness_counts_as_invalid_not_correct() -> None:
    trials = [_FakeTrial("letter-detective", True), _FakeTrial("letter-detective", None), _FakeTrial("letter-detective", None)]
    skill = build_domain_skill("visual-symbol-discrimination", trials, PERSONALIZATION_CONFIG)
    assert skill.evidence_state == "insufficient_data"
    assert skill.valid_trial_count == 1


# ---- M: missing speech/gaze still works -----------------------------------

def test_behavior_only_personalization_works_without_speech_gaze() -> None:
    # The whole personalization pipeline consumes only Trial/GameSession rows.
    trials = _fake_trials("sequence-quest", [True, True, True, True, True])
    skill = build_domain_skill("working-memory", trials, PERSONALIZATION_CONFIG)
    assert skill.evidence_state == "sufficient_data"
    assert skill.category == "relative_strength"


# ---- N: determinism ------------------------------------------------------

def test_personalization_is_deterministic(client: TestClient) -> None:
    child = client.post("/api/children", json={"display_name": "Explorer", "birth_year": 2018}).json()
    assessment = client.post("/api/assessments", json={"child_id": child["id"]}).json()
    for i, (game, correct) in enumerate(
        [(g, c) for g, c in (("letter-detective", True), ("word-flash", True), ("sequence-quest", False)) for _ in range(3)]
    ):
        client.post(
            f"/api/assessments/{assessment['id']}/games/{game}/trials",
            json={
                "trial_number": i + 1,
                "stimulus": {"target": "b", "options": ["b", "d"]},
                "expected_response": "b",
                "game_version": "1.0.0",
                "domain": GAME_DOMAIN[game],
                "difficulty": 2,
                "correctness": correct,
                "completed_at": "2026-01-01T12:00:05.000Z",
            },
        )
    first = client.get(f"/api/personalization/children/{child['id']}/profile").json()
    second = client.get(f"/api/personalization/children/{child['id']}/profile").json()
    assert first == second


# ---- P: progress / trends -------------------------------------------------

def test_progress_compares_earliest_and_latest_assessment(client: TestClient) -> None:
    child = client.post("/api/children", json={"display_name": "Explorer", "birth_year": 2018}).json()
    for run, correct in ((1, True), (2, False)):
        assessment = client.post("/api/assessments", json={"child_id": child["id"]}).json()
        for i in range(3):
            client.post(
                f"/api/assessments/{assessment['id']}/games/letter-detective/trials",
                json={
                    "trial_number": i + 1,
                    "stimulus": {"target": "b", "options": ["b", "d"]},
                    "expected_response": "b",
                    "game_version": "1.0.0",
                    "domain": "visual-symbol-discrimination",
                    "difficulty": 2,
                    "correctness": correct,
                    "completed_at": f"2026-0{run}-01T12:00:0{i + 1}.000Z",
                },
            )
        client.post(f"/api/assessments/{assessment['id']}/summary", json={"games": [], "total_trials": 3})
    # An abandoned (planned) session with trials must not shift the comparison.
    abandoned = client.post("/api/assessments", json={"child_id": child["id"]}).json()
    client.post(
        f"/api/assessments/{abandoned['id']}/games/letter-detective/trials",
        json={
            "trial_number": 1,
            "stimulus": {"target": "b", "options": ["b", "d"]},
            "expected_response": "b",
            "game_version": "1.0.0",
            "domain": "visual-symbol-discrimination",
            "difficulty": 2,
            "correctness": True,
            "completed_at": "2026-01-03T12:00:01.000Z",
        },
    )
    progress = client.get(f"/api/personalization/children/{child['id']}/progress")
    assert progress.status_code == 200
    body = progress.json()
    assert len(body["points"]) == 2
    assert body["comparison"] is not None
    delta = body["comparison"]["domains"]["visual-symbol-discrimination"]["delta"]
    assert delta == pytest.approx(-1.0)


# ---- Q: versioning / reproducibility ---------------------------------------

def test_engine_and_schema_version_present_with_config_summary(client: TestClient) -> None:
    child = client.post("/api/children", json={"display_name": "Explorer", "birth_year": 2018}).json()
    profile = client.get(f"/api/personalization/children/{child['id']}/profile")
    assert profile.json()["engine_version"] == "1.0.0"
    assert profile.json()["schema_version"] == "1.0"
    assert profile.json()["config_summary"]["engine_version"] == "1.0.0"
    # config decisions are auditable (documented as non-clinical thresholds)
    assert "config" in profile.json()["config_summary"]


# ---- R: safe default difficulty -------------------------------------------

def test_difficulty_safe_default_without_evidence(client: TestClient) -> None:
    rules = PERSONALIZATION_CONFIG.difficulty
    decision = decide("word-maze", [], rules, current_level=None)
    assert decision.level == rules.default_level
    assert decision.changed is False


# ---- S: evidence.state helper sanity ----------------------------------------

def test_difficulty_insufficient_evidence_holds_level() -> None:
    rules = PERSONALIZATION_CONFIG.difficulty
    decision = decide("word-maze", [_FakeTrial("word-maze", None)], rules, current_level=3)
    assert decision.level == 3
    assert decision.changed is False