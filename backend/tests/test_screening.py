"""Screening pipeline and API tests.

SOFTWARE-ENGINEERING TESTS ONLY. All models here are trained on synthetic
simulator data. The "eligible" fixture below is a deliberately fabricated model
card used to exercise the code path that a genuinely validated model would take;
passing these tests says nothing about real-world screening performance.
"""

from __future__ import annotations

import hashlib
import json
import pickle
import shutil
from pathlib import Path
from uuid import UUID

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.database import SessionLocal
from app.ml.screening.model import ScreeningModel
from app.ml.screening.registry import evaluate_eligibility, load_registry
from app.ml.screening.schema import FEATURE_NAMES, SCREENING_SCHEMA_VERSION, TARGET_ID, assert_schema_is_leak_free, validate_features
from app.ml.screening.training import grouped_split, prepare_rows, synthetic_rows, train_screening_model
from app.models import ScreeningResult
from tests.helpers import trial_payload


# --- fixtures -------------------------------------------------------------------------

@pytest.fixture(scope="module")
def synthetic_model_dir(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("synthetic") / "demo"
    train_screening_model(
        synthetic_rows(seed=7, subjects=120), out, training_data="synthetic",
        provenance={"source": "simulator"}, model_id="synthetic-demo", version="0.0.1", seed=7,
    )
    return out


def _fabricate_eligible(synthetic_dir: Path, target: Path, version: str = "1.0.0", **card_overrides) -> Path:
    """ENGINEERING FIXTURE: relabel a synthetic artifact as if it had passed real validation."""
    target.mkdir(parents=True, exist_ok=True)
    model: ScreeningModel = pickle.loads((synthetic_dir / "model.pkl").read_bytes())
    model.training_data = "real"
    model.output_type = "calibrated_probability"
    model.target_id = TARGET_ID
    data = pickle.dumps(model)
    (target / "model.pkl").write_bytes(data)
    card = json.loads((synthetic_dir / "model_card.json").read_text())
    card.update(
        model_id="fixture-eligible", version=version, training_data="real", output_type="calibrated_probability",
        designation="clinical_screening_candidate", target_id=TARGET_ID,
        artifact_sha256=hashlib.sha256(data).hexdigest(), created_at=f"2026-01-01T00:00:0{version[0]}",
    )
    card["evaluation"]["reliable_sample_size"] = True
    card["validation"].update(
        external_validation_reference="FIXTURE-NOT-REAL", specialist_review_reference="FIXTURE-NOT-REAL",
        ethics_approval_reference="FIXTURE-NOT-REAL", approved_thresholds=[{"min": 0.0, "key": "lower"}, {"min": 0.5, "key": "higher"}],
        intended_population={"age_min": 5, "age_max": 9, "languages": ["en"]}, min_scored_trials=15,
    )
    card.update(card_overrides)
    (target / "model_card.json").write_text(json.dumps(card))
    return target


@pytest.fixture
def registry_dir(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(get_settings(), "screening_model_dir", str(tmp_path))
    return tmp_path


def _completed_assessment(client: TestClient, trials: int = 18, language: str = "en", birth_year: int | None = 2019) -> tuple[dict, dict]:
    child = client.post("/api/children", json={"display_name": "Ava", **({"birth_year": birth_year} if birth_year else {})}).json()
    assessment = client.post("/api/assessments", json={"child_id": child["id"], "language": language}).json()
    games = ["letter-detective", "word-flash", "sequence-quest", "mirror-match"]
    for index in range(trials):
        game = games[index % len(games)]
        payload = trial_payload(game, index + 1, index % 3 != 0, domain={"letter-detective": "visual-symbol-discrimination", "mirror-match": "visual-symbol-discrimination", "word-flash": "orthographic-recognition", "sequence-quest": "working-memory"}[game], reaction_time_ms=900 + index * 20)
        assert client.post(f"/api/assessments/{assessment['id']}/games/{game}/trials", json=payload).status_code == 201
    assert client.post(f"/api/assessments/{assessment['id']}/summary", json={"games": [], "total_trials": trials}).status_code == 201
    return child, assessment


# --- schema & data --------------------------------------------------------------------

def test_schema_has_no_identifier_or_label_features() -> None:
    assert_schema_is_leak_free()
    for bad in ("child_id", "subject_label", "scenario", "risk_score"):
        with pytest.raises(ValueError):
            assert_schema_is_leak_free((bad,))


def test_missing_features_stay_missing_and_invalid_are_rejected() -> None:
    result = validate_features({"overall_accuracy": {"value": 0.8, "available": True}, "median_reaction_time_ms": 900, "completion_rate": 1})
    assert result.ok
    assert result.vector["speech_error_rate"] is None  # not 0
    assert "speech_error_rate" in result.missing_optional
    missing = validate_features({"overall_accuracy": 0.8})
    assert not missing.ok and "median_reaction_time_ms" in missing.missing_required
    invalid = validate_features({"overall_accuracy": 1.5, "median_reaction_time_ms": float("nan"), "completion_rate": True})
    assert set(invalid.invalid) == {"overall_accuracy", "median_reaction_time_ms", "completion_rate"}
    unavailable = validate_features({"overall_accuracy": {"value": 0.9, "available": False}})
    assert unavailable.vector["overall_accuracy"] is None


def test_grouped_split_never_leaks_participants_and_is_reproducible() -> None:
    rows, _ = prepare_rows(synthetic_rows(seed=3, subjects=80))
    first, second = grouped_split(rows, seed=11), grouped_split(rows, seed=11)
    ids = {name: {row.participant_id for row in part} for name, part in first.items()}
    assert not (ids["train"] & ids["test"]) and not (ids["train"] & ids["validation"]) and not (ids["validation"] & ids["test"])
    assert [r.participant_id for r in first["test"]] == [r.participant_id for r in second["test"]]


def test_training_is_reproducible_and_honestly_labelled(synthetic_model_dir: Path, tmp_path: Path) -> None:
    card = json.loads((synthetic_model_dir / "model_card.json").read_text())
    again = train_screening_model(synthetic_rows(seed=7, subjects=120), tmp_path / "again", training_data="synthetic", provenance={"source": "simulator"}, model_id="synthetic-demo", version="0.0.1", seed=7)
    assert card["evaluation"]["test"]["estimate"] == again["evaluation"]["test"]["estimate"]
    assert card["model_selection"] == again["model_selection"]
    assert card["training_data"] == "synthetic"
    assert card["output_type"] == "research_score"  # validation set too small to calibrate
    assert card["evaluation"]["reliable_sample_size"] is False
    assert card["candidate_threshold"]["status"] == "requires_specialist_approval"
    assert card["validation"]["approved_thresholds"] == []
    for key in ("roc_auc", "pr_auc", "brier", "sensitivity", "specificity", "ppv", "npv"):
        assert key in card["evaluation"]["test"]["estimate"]


def test_real_training_requires_provenance(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="provenance"):
        train_screening_model(synthetic_rows(seed=1, subjects=40), tmp_path, training_data="real", provenance={"source": "x"}, model_id="m", version="1")


# --- registry & eligibility ----------------------------------------------------------

def test_synthetic_models_are_never_eligible(synthetic_model_dir: Path, registry_dir: Path) -> None:
    shutil.copytree(synthetic_model_dir, registry_dir / "synthetic")
    [entry] = load_registry(registry_dir)
    assert not entry.eligible
    assert "model was not trained on real labelled data" in entry.reasons
    assert "artifact provenance is synthetic" in entry.reasons


def test_editing_the_card_cannot_promote_a_synthetic_artifact(synthetic_model_dir: Path, registry_dir: Path) -> None:
    target = shutil.copytree(synthetic_model_dir, registry_dir / "edited")
    card = json.loads((target / "model_card.json").read_text())
    card.update(training_data="real", output_type="calibrated_probability")
    card["evaluation"]["reliable_sample_size"] = True
    card["validation"].update(external_validation_reference="x", specialist_review_reference="x", ethics_approval_reference="x", intended_population={"age_min": 5, "age_max": 9, "languages": ["en"]})
    (target / "model_card.json").write_text(json.dumps(card))
    [entry] = load_registry(registry_dir)
    assert not entry.eligible and "artifact provenance is synthetic" in entry.reasons


def test_tampered_or_traversing_artifacts_are_rejected(synthetic_model_dir: Path, registry_dir: Path) -> None:
    eligible = _fabricate_eligible(synthetic_model_dir, registry_dir / "ok")
    (eligible / "model.pkl").write_bytes((eligible / "model.pkl").read_bytes() + b"tamper")
    traversal = _fabricate_eligible(synthetic_model_dir, registry_dir / "trav", artifact="../ok/model.pkl")
    reasons = {entry.card["model_id"] + entry.card.get("artifact", ""): entry.reasons for entry in load_registry(registry_dir)}
    assert any("SHA-256" in " ".join(r) for r in reasons.values())
    assert any("plain file name" in " ".join(r) for r in reasons.values())
    assert traversal.exists()


def test_eligibility_requires_every_evidence_field(synthetic_model_dir: Path, registry_dir: Path) -> None:
    _fabricate_eligible(synthetic_model_dir, registry_dir / "ok")
    [entry] = load_registry(registry_dir)
    assert entry.eligible, entry.reasons
    for key in ("external_validation_reference", "specialist_review_reference", "ethics_approval_reference"):
        card = json.loads(json.dumps(entry.card))
        card["validation"][key] = None
        assert evaluate_eligibility(card, entry.model)
    card = json.loads(json.dumps(entry.card))
    card["feature_schema_version"] = "screening-0.9"
    assert "feature schema version is incompatible" in evaluate_eligibility(card, entry.model)


# --- API ------------------------------------------------------------------------------

def test_without_eligible_model_no_score_is_produced(client: TestClient, registry_dir: Path, synthetic_model_dir: Path) -> None:
    shutil.copytree(synthetic_model_dir, registry_dir / "synthetic")
    child, assessment = _completed_assessment(client)
    body = client.get(f"/api/screening/children/{child['id']}").json()
    assert body["status"] == "no_eligible_model"
    assert body["result"] is None and body["model"] is None
    assert "model was not trained on real labelled data" in body["reasons"]
    assert body["observations"]["scored_trials"] == 18
    assert body["assessment_id"] == assessment["id"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ScreeningResult)) == 0


def test_no_and_incomplete_assessment_states(client: TestClient, registry_dir: Path) -> None:
    child = client.post("/api/children", json={"display_name": "New"}).json()
    assert client.get(f"/api/screening/children/{child['id']}").json()["status"] == "no_assessment"
    client.post("/api/assessments", json={"child_id": child["id"]})
    assert client.get(f"/api/screening/children/{child['id']}").json()["status"] == "assessment_incomplete"


def test_screening_authorization(client: TestClient, anon_client: TestClient, make_client, registry_dir: Path) -> None:
    child, _ = _completed_assessment(client, trials=4)
    assert anon_client.get(f"/api/screening/children/{child['id']}").status_code == 401
    assert make_client("parent").get(f"/api/screening/children/{child['id']}").status_code == 404
    educator = make_client("educator")
    assert educator.get(f"/api/screening/children/{child['id']}").status_code == 404
    client.post(f"/api/children/{child['id']}/educators", json={"educator_email": educator.user.email})
    assert educator.get(f"/api/screening/children/{child['id']}").status_code == 200


def test_eligible_fixture_produces_one_stored_versioned_result(client: TestClient, registry_dir: Path, synthetic_model_dir: Path) -> None:
    _fabricate_eligible(synthetic_model_dir, registry_dir / "ok")
    child, assessment = _completed_assessment(client)
    first = client.get(f"/api/screening/children/{child['id']}").json()
    assert first["status"] == "available", first["reasons"]
    assert 0 <= first["result"]["score"] <= 1
    assert first["result"]["output_type"] == "calibrated_probability"
    assert first["result"]["band"] in {"lower", "higher"}
    assert first["model"] == {"model_id": "fixture-eligible", "model_version": "1.0.0", "model_name": first["model"]["model_name"], "output_type": "calibrated_probability", "feature_schema_version": SCREENING_SCHEMA_VERSION}
    second = client.get(f"/api/screening/children/{child['id']}").json()
    assert second["result"] == first["result"]
    _fabricate_eligible(synthetic_model_dir, registry_dir / "v2", version="2.0.0")
    third = client.get(f"/api/screening/children/{child['id']}").json()
    assert third["model"]["model_version"] == "2.0.0"
    with SessionLocal() as db:
        rows = db.scalars(select(ScreeningResult).where(ScreeningResult.assessment_id == UUID(assessment["id"]))).all()
        assert sorted(row.model_version for row in rows) == ["1.0.0", "2.0.0"]
        assert all(row.feature_schema_version == SCREENING_SCHEMA_VERSION for row in rows)
    # Deleting the child deletes its screening history.
    assert client.delete(f"/api/children/{child['id']}").status_code == 204
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ScreeningResult).where(ScreeningResult.assessment_id == UUID(assessment["id"]))) == 0


@pytest.mark.parametrize(
    "kwargs,status_",
    [({"trials": 8}, "insufficient_observations"), ({"language": "ta"}, "unsupported_population"), ({"birth_year": 2012}, "unsupported_population"), ({"birth_year": None}, "unsupported_population")],
)
def test_input_requirements_block_prediction(client: TestClient, registry_dir: Path, synthetic_model_dir: Path, kwargs, status_) -> None:
    _fabricate_eligible(synthetic_model_dir, registry_dir / "ok")
    child, _ = _completed_assessment(client, **kwargs)
    body = client.get(f"/api/screening/children/{child['id']}").json()
    assert body["status"] == status_ and body["result"] is None


def test_unscored_trials_are_not_counted_as_errors(client: TestClient, registry_dir: Path) -> None:
    child = client.post("/api/children", json={"display_name": "U"}).json()
    assessment = client.post("/api/assessments", json={"child_id": child["id"]}).json()
    client.post(f"/api/assessments/{assessment['id']}/games/sound-quest-adventure/trials", json=trial_payload("sound-quest-adventure", 1, None, domain="phonological-awareness"))
    client.post(f"/api/assessments/{assessment['id']}/summary", json={"games": [], "total_trials": 1})
    observations = client.get(f"/api/screening/children/{child['id']}").json()["observations"]
    assert observations == {**observations, "scored_trials": 0, "unscored_trials": 1}


def test_research_demo_is_admin_only_and_off_by_default(client: TestClient, make_client, synthetic_model_dir: Path, monkeypatch) -> None:
    _, assessment = _completed_assessment(client, trials=4)
    admin = make_client("admin")
    path = f"/api/screening/research-demo/assessments/{assessment['id']}"
    assert admin.get(path).status_code == 404  # disabled by default
    monkeypatch.setattr(get_settings(), "research_demo_enabled", True)
    monkeypatch.setattr(get_settings(), "research_demo_model_dir", str(synthetic_model_dir.parent))
    assert client.get(path).status_code == 403
    body = admin.get(path).json()
    assert body["label"].startswith("Synthetic research score")
    assert body["outputs"] and body["outputs"][0]["model_id"] == "synthetic-demo"
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ScreeningResult).where(ScreeningResult.assessment_id == UUID(assessment["id"]))) == 0


def test_feature_matrix_preserves_missingness(synthetic_model_dir: Path) -> None:
    model: ScreeningModel = pickle.loads((synthetic_model_dir / "model.pkl").read_bytes())
    matrix = model.matrix([{name: None for name in FEATURE_NAMES}])
    assert np.isnan(matrix).all()


def test_concurrent_feature_extraction_does_not_fail(client: TestClient, registry_dir: Path) -> None:
    """Dashboard cards request the same assessment's features in parallel."""
    from concurrent.futures import ThreadPoolExecutor

    child, assessment = _completed_assessment(client, trials=6)
    paths = [f"/api/screening/children/{child['id']}", f"/api/ml/profile/session/{assessment['id']}"] * 4
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(lambda path: client.get(path).status_code, paths))
    assert statuses == [200] * len(paths)
