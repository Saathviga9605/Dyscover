"""Synthetic research predictor: dataset, training, artifact, registry separation, API.

The model under test is trained on SYNTHETIC data. These tests verify software
behaviour (that real stored game observations reach the trained model, that
outputs stay out of clinical records, that no bypass exists) — not dyslexia
detection accuracy.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from uuid import UUID

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import ConfigurationError, Settings, get_settings
from app.database import SessionLocal
from app.ml.screening.registry import active_research_model, load_registry, load_research_registry
from app.ml.screening.research_data import POSITIVE_PROFILES, RESEARCH_TARGET_ID, TRAINABLE_PROFILES, VISUAL_RUN, generate_research_dataset
from app.ml.screening.schema import FEATURE_NAMES, validate_features
from app.ml.screening.training import LeakageError, _matrix, check_leakage, evaluate, grouped_split, prepare_rows, train_screening_model
from app.ml.service import extract_profile
from app.models import ResearchPrediction, ScreeningResult
from tests.helpers import trial_payload

BACKEND = Path(__file__).resolve().parents[1]
SHIPPED = BACKEND / "artifacts" / "screening-synthetic"
SHIPPED_MODEL = SHIPPED / "dyscover-research-synthetic"
DOMAINS = {
    "letter-detective": "visual-symbol-discrimination",
    "mirror-match": "visual-symbol-discrimination",
    "word-flash": "orthographic-recognition",
    "sequence-quest": "working-memory",
    "word-maze": "attention-visual-search",
}


@pytest.fixture
def research_on(monkeypatch) -> Path:
    monkeypatch.setattr(get_settings(), "research_demo_enabled", True)
    monkeypatch.setattr(get_settings(), "research_demo_model_dir", str(SHIPPED))
    return SHIPPED


@pytest.fixture(scope="module")
def small_model(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("research") / "small"
    train_screening_model(generate_research_dataset(seed=5, participants=160)["rows"], out, training_data="synthetic", provenance={"source": "simulator"}, model_id="small-research", version="0.0.1", seed=5)
    return out


def _visual_run(client: TestClient, language: str = "en", birth_year: int | None = 2019, games=VISUAL_RUN, complete: bool = True) -> tuple[dict, dict]:
    """Plays the visual run through the real API (server-side scoring, real storage)."""
    child = client.post("/api/children", json={"display_name": "Ava", **({"birth_year": birth_year} if birth_year else {})}).json()
    assessment = client.post("/api/assessments", json={"child_id": child["id"], "language": language}).json()
    number = 0
    for game, count in games:
        for index in range(count):
            number += 1
            payload = trial_payload(game, number, (number % 4) != 0, domain=DOMAINS.get(game, "phonological-awareness"), reaction_time_ms=850 + 37 * number, hesitation_time_ms=90 + 5 * number)
            assert client.post(f"/api/assessments/{assessment['id']}/games/{game}/trials", json=payload).status_code == 201
    if complete:
        assert client.post(f"/api/assessments/{assessment['id']}/summary", json={"games": [], "total_trials": number}).status_code == 201
    return child, assessment


def _find(data, key):
    """All entries of non-empty lists stored under ``key`` anywhere in a nested export."""
    if isinstance(data, dict):
        for name, value in data.items():
            if name == key and value:
                yield from value
            else:
                yield from _find(value, key)
    elif isinstance(data, list):
        for value in data:
            yield from _find(value, key)


def _predict(client: TestClient, child: dict, assessment: dict):
    return client.post(f"/api/screening/research/children/{child['id']}/assessments/{assessment['id']}/predict")


# --- dataset --------------------------------------------------------------------------

def test_dataset_is_deterministic_and_follows_the_documented_label_rule() -> None:
    first, again, other = generate_research_dataset(seed=11, participants=40), generate_research_dataset(seed=11, participants=40), generate_research_dataset(seed=12, participants=40)
    assert first["metadata"]["data_checksum"] == again["metadata"]["data_checksum"] != other["metadata"]["data_checksum"]
    assert first["metadata"]["synthetic"] is True and first["metadata"]["target_id"] == RESEARCH_TARGET_ID
    for row in first["rows"]:
        index = int(row["participant_id"].rsplit("-", 1)[1])
        assert row["label"] == int(TRAINABLE_PROFILES[index % len(TRAINABLE_PROFILES)] in POSITIVE_PROFILES)
        assert set(row["features"]) == set(FEATURE_NAMES)  # exactly the schema; no IDs or labels
        assert row["features"]["speech_error_rate"] is None  # the visual run records no speech; not 0
        assert all(row["features"][f"domain_{d}_accuracy"] is not None for d in set(DOMAINS.values()))
    gaze = [row["features"]["gaze_regression_count"] for row in first["rows"]]
    assert None in gaze and any(value is not None for value in gaze)  # missing modality stays missing
    assert sum(count for _, count in VISUAL_RUN) == 22


def test_prepare_rows_handles_duplicates_contradictions_and_malformed_rows() -> None:
    good = generate_research_dataset(seed=2, participants=8)["rows"]
    rows = [*good, good[0], {**good[1], "label": 1 - good[1]["label"], "features": {**good[1]["features"], "overall_accuracy": 0.01}}, {**good[2], "participant_id": ""}, {**good[3], "label": "maybe"}, {**good[4], "features": {**good[4]["features"], "overall_accuracy": float("nan")}}]
    prepared, excluded = prepare_rows(rows)
    assert excluded["duplicate"] == 1 and excluded["missing_participant"] == 1 and excluded["invalid_label"] == 1 and excluded["invalid_features"] == 1
    assert excluded["contradictory_label"] == 3  # both rows of participant 1 plus the contradicting one
    assert good[1]["participant_id"] not in {row.participant_id for row in prepared}


# --- training -------------------------------------------------------------------------

def test_leakage_check_fails_on_an_intentionally_leaking_feature(tmp_path: Path) -> None:
    rows = generate_research_dataset(seed=3, participants=160)["rows"]
    x, y = _matrix(prepare_rows(rows)[0])
    check_leakage(x, y, FEATURE_NAMES)  # the genuine features pass
    leaked = [{**row, "features": {**row["features"], "completion_rate": 0.5 + 0.4 * row["label"]}} for row in rows]
    with pytest.raises(LeakageError, match="completion_rate"):
        train_screening_model(leaked, tmp_path, training_data="synthetic", provenance={}, model_id="leak", version="0")
    with pytest.raises(ValueError):
        check_leakage(x[:, :1], y, ("participant_id",))


def test_preprocessing_is_fitted_on_training_participants_only(small_model: Path) -> None:
    import pickle

    card = json.loads((small_model / "model_card.json").read_text())
    model = pickle.loads((small_model / "model.pkl").read_bytes())
    split = grouped_split(prepare_rows(generate_research_dataset(seed=5, participants=160)["rows"])[0], 5)
    x_train, _ = _matrix(split["train"])
    x_all, _ = _matrix(split["train"] + split["validation"] + split["test"])
    pipeline = model.pipeline if hasattr(model.pipeline, "named_steps") else model.pipeline.calibrated_classifiers_[0].estimator.estimator
    statistics = pipeline.named_steps["impute"].statistics_
    column = FEATURE_NAMES.index("median_reaction_time_ms")
    assert statistics[column] == pytest.approx(np.nanmedian(x_train[:, column]))
    assert statistics[column] != pytest.approx(np.nanmedian(x_all[:, column]))
    assert card["feature_reference"]["median_reaction_time_ms"]["median"] == pytest.approx(np.nanmedian(x_train[:, column]))
    participants = card["data_summary"]["participants"]
    assert participants["train"] + participants["validation"] + participants["test"] == 160


def test_candidates_are_compared_with_a_baseline_on_validation(small_model: Path) -> None:
    card = json.loads((small_model / "model_card.json").read_text())
    algorithms = {entry["algorithm"] for entry in card["model_selection"]}
    assert algorithms == {"dummy_prior", "logistic_regression", "random_forest", "gradient_boosting"}
    best = max((e for e in card["model_selection"] if e["algorithm"] != "dummy_prior"), key=lambda e: e["validation_roc_auc"])
    assert (card["algorithm"], card["hyperparameters"]) == (best["algorithm"], best["hyperparameters"])
    assert card["evaluation"]["dummy_baseline_test"]["roc_auc"] == 0.5
    # 32 test participants: honestly flagged as unreliable and uncalibrated.
    assert card["evaluation"]["reliable_sample_size"] is False and card["output_type"] == "research_score"
    assert card["evaluation"]["test"]["confusion_at_threshold"] is not None


def test_undefined_metrics_are_reported_as_none_not_guessed() -> None:
    result = evaluate(np.array([0, 0, 0]), np.array([0.1, 0.2, 0.3]), ["a", "b", "c"], 0.5, seed=1, bootstrap=50)
    assert result["estimate"]["roc_auc"] is None and result["estimate"]["pr_auc"] is None
    assert result["estimate"]["sensitivity"] is None and result["estimate"]["ppv"] is None
    assert all(value is None for value in result["ci95"].values())


def test_partition_without_both_classes_is_refused(tmp_path: Path) -> None:
    rows = generate_research_dataset(seed=4, participants=16)["rows"]
    rows = [row for row in rows if row["label"] == 0] + [row for row in rows if row["label"] == 1][:2]
    with pytest.raises(ValueError, match="lacks one outcome class"):
        train_screening_model(rows, tmp_path, training_data="synthetic", provenance={}, model_id="tiny", version="0")


# --- shipped artifact -----------------------------------------------------------------

def test_shipped_artifact_is_complete_and_checksummed() -> None:
    card = json.loads((SHIPPED_MODEL / "model_card.json").read_text())
    assert hashlib.sha256((SHIPPED_MODEL / "model.pkl").read_bytes()).hexdigest() == card["artifact_sha256"]
    assert card["designation"] == "synthetic_research" and card["training_data"] == "synthetic" and card["target_id"] == RESEARCH_TARGET_ID
    for key in ("feature_names", "feature_schema_version", "target_definition", "seed", "runtime", "training_config", "model_selection", "evaluation", "leakage_check", "feature_reference", "provenance", "research_inputs"):
        assert card[key], key
    assert card["provenance"]["dataset"]["data_checksum"]
    assert card["evaluation"]["test"]["counts"]["participants"] >= 100


def test_shipped_artifact_loads_in_a_fresh_process() -> None:
    code = (
        "import json, pathlib; from app.ml.screening.registry import load_research_registry;"
        f"[m] = load_research_registry(pathlib.Path(r'{SHIPPED}'));"
        "print(json.dumps({'eligible': m.eligible, 'reasons': m.reasons, 'score': m.model.score([{'overall_accuracy': 0.5, 'median_reaction_time_ms': 1200, 'completion_rate': 1.0}])[0]}))"
    )
    output = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True, check=True, timeout=120).stdout
    result = json.loads(output.strip().splitlines()[-1])
    assert result["eligible"] and not result["reasons"] and 0 <= result["score"] <= 1


def test_corrupted_or_incompatible_research_artifacts_fail_safely(tmp_path: Path) -> None:
    corrupt = shutil.copytree(SHIPPED_MODEL, tmp_path / "corrupt")
    (corrupt / "model.pkl").write_bytes(b"not a pickle")
    card = json.loads((corrupt / "model_card.json").read_text())
    card["artifact_sha256"] = hashlib.sha256(b"not a pickle").hexdigest()
    (corrupt / "model_card.json").write_text(json.dumps(card))
    old = shutil.copytree(SHIPPED_MODEL, tmp_path / "old-runtime")
    card = json.loads((old / "model_card.json").read_text())
    card["runtime"]["scikit_learn"] = "0.24.2"
    (old / "model_card.json").write_text(json.dumps(card))
    tampered = shutil.copytree(SHIPPED_MODEL, tmp_path / "tampered")
    (tampered / "model.pkl").write_bytes((tampered / "model.pkl").read_bytes() + b"x")
    entries = load_research_registry(tmp_path)
    assert len(entries) == 3 and not any(entry.eligible for entry in entries)
    flat = " ".join(" ".join(entry.reasons) for entry in entries)
    assert "could not be loaded" in flat and "scikit-learn 0.24.2" in flat and "SHA-256" in flat
    assert active_research_model(tmp_path)[0] is None


# --- research / production separation -------------------------------------------------

def test_research_model_is_never_eligible_for_production_even_if_pointed_at(monkeypatch) -> None:
    [entry] = load_registry(SHIPPED)
    assert not entry.eligible
    assert {"model is designated for synthetic research only", "artifact provenance is synthetic", "artifact targets a different outcome"} <= set(entry.reasons)


def test_relabelled_card_is_refused_by_both_registries(tmp_path: Path) -> None:
    edited = shutil.copytree(SHIPPED_MODEL, tmp_path / "edited")
    card = json.loads((edited / "model_card.json").read_text())
    card.update(designation="clinical_screening_candidate", training_data="real", target_id="elevated_reading_difficulty_risk_v1")
    card["evaluation"]["reliable_sample_size"] = True
    card["validation"].update(external_validation_reference="x", specialist_review_reference="x", ethics_approval_reference="x", intended_population={"age_min": 4, "age_max": 10, "languages": ["en"]})
    (edited / "model_card.json").write_text(json.dumps(card))
    [production] = load_registry(tmp_path)
    assert not production.eligible and "artifact provenance is synthetic" in production.reasons
    [research] = load_research_registry(tmp_path)
    assert not research.eligible and "model card is not a synthetic research model" in research.reasons


def test_production_settings_refuse_research_mode() -> None:
    with pytest.raises(ConfigurationError, match="RESEARCH_DEMO_ENABLED"):
        Settings(app_env="production", secret_key="x" * 64, research_demo_enabled=True)


def test_parent_screening_card_never_falls_back_to_the_research_model(client: TestClient, research_on: Path, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(get_settings(), "screening_model_dir", str(tmp_path))
    child, assessment = _visual_run(client)
    assert _predict(client, child, assessment).json()["status"] == "available"
    body = client.get(f"/api/screening/children/{child['id']}").json()
    assert body["status"] == "no_eligible_model" and body["result"] is None and body["model"] is None
    # Even with the production directory pointed at the research artifacts.
    monkeypatch.setattr(get_settings(), "screening_model_dir", str(SHIPPED))
    body = client.get(f"/api/screening/children/{child['id']}").json()
    assert body["status"] == "no_eligible_model" and body["result"] is None
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ScreeningResult).where(ScreeningResult.assessment_id == UUID(assessment["id"]))) == 0


# --- API: real game observations -> trained model ---------------------------------------

def test_real_stored_game_observations_reach_the_trained_model(client: TestClient, research_on: Path) -> None:
    child, assessment = _visual_run(client)
    response = _predict(client, child, assessment)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "available", body["reasons"]
    assert body["observations"]["scored_trials"] == 22
    assert body["model"]["model_id"] == "dyscover-research-synthetic" and body["model"]["designation"] == "synthetic_research"
    assert body["label"].startswith("Synthetic research score") and "NOT a real-child dyslexia probability" in body["label"]
    # The score is exactly the shipped model applied to the features extracted from the stored trials.
    with SessionLocal() as db:
        features = validate_features(extract_profile(db, UUID(assessment["id"]))[0])
    model, _ = active_research_model(SHIPPED)
    assert body["result"]["score"] == pytest.approx(model.model.score([features.vector])[0])
    assert features.vector["overall_accuracy"] == pytest.approx(17 / 22)
    shown = {item["name"]: item for item in body["features"]}
    assert shown["overall_accuracy"]["value"] == pytest.approx(17 / 22)
    assert shown["speech_error_rate"]["available"] is False and shown["speech_error_rate"]["value"] is None
    assert any(item["score_change_if_typical"] for item in body["features"])
    assert "model.pkl" not in json.dumps(body) and "pipeline" not in body["model"]


def test_research_prediction_is_stored_once_separately_and_exported_and_deleted(client: TestClient, research_on: Path) -> None:
    child, assessment = _visual_run(client)
    first, second = _predict(client, child, assessment).json(), _predict(client, child, assessment).json()
    assert first["result"] == second["result"]
    with SessionLocal() as db:
        rows = db.scalars(select(ResearchPrediction).where(ResearchPrediction.assessment_id == UUID(assessment["id"]))).all()
        assert len(rows) == 1 and rows[0].target_id == RESEARCH_TARGET_ID and rows[0].model_version == "1.0.0"
        assert db.scalar(select(func.count()).select_from(ScreeningResult).where(ScreeningResult.assessment_id == UUID(assessment["id"]))) == 0
    overview = client.get(f"/api/screening/research/children/{child['id']}").json()
    assert overview["assessments"][0]["has_prediction"] is True
    archive = zipfile.ZipFile(io.BytesIO(client.get("/api/privacy/export").content))
    exported = json.loads(archive.read("user_data.json").decode("utf-8"))
    [stored] = list(_find(exported, "research_predictions"))
    assert stored["score"] == pytest.approx(first["result"]["score"])
    assert client.delete(f"/api/children/{child['id']}").status_code == 204
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ResearchPrediction).where(ResearchPrediction.assessment_id == UUID(assessment["id"]))) == 0


def test_changed_artifact_under_same_version_is_refused(client: TestClient, research_on: Path) -> None:
    child, assessment = _visual_run(client)
    _predict(client, child, assessment)
    with SessionLocal() as db:
        row = db.scalar(select(ResearchPrediction).where(ResearchPrediction.assessment_id == UUID(assessment["id"])))
        row.artifact_sha256 = "0" * 64
        db.commit()
    body = _predict(client, child, assessment).json()
    assert body["status"] == "model_version_conflict" and body["result"] is None


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({"games": (("letter-detective", 5), ("mirror-match", 3))}, "insufficient_observations"),
        ({"games": (("letter-detective", 5), ("mirror-match", 5), ("word-flash", 5), ("sequence-quest", 4))}, "insufficient_observations"),
        ({"games": (("sound-quest-adventure", 9), ("letter-bubble-pop", 9))}, "insufficient_observations"),
        ({"language": "ta"}, "unsupported_population"),
        ({"birth_year": 2012}, "unsupported_population"),
        ({"complete": False}, "assessment_incomplete"),
    ],
)
def test_inputs_that_cannot_be_scored_get_an_explicit_status(client: TestClient, research_on: Path, kwargs, expected) -> None:
    child, assessment = _visual_run(client, **kwargs)
    body = _predict(client, child, assessment).json()
    assert body["status"] == expected, body
    assert body["result"] is None
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ResearchPrediction).where(ResearchPrediction.assessment_id == UUID(assessment["id"]))) == 0


def test_unknown_age_is_scored_with_an_explicit_note(client: TestClient, research_on: Path) -> None:
    child, assessment = _visual_run(client, birth_year=None)
    body = _predict(client, child, assessment).json()
    assert body["status"] == "available" and any("Age is not recorded" in note for note in body["notes"])


def test_missing_or_broken_research_model_returns_a_status(client: TestClient, research_on: Path, monkeypatch, tmp_path: Path) -> None:
    child, assessment = _visual_run(client)
    monkeypatch.setattr(get_settings(), "research_demo_model_dir", str(tmp_path))
    assert _predict(client, child, assessment).json()["status"] == "no_research_model"
    broken = shutil.copytree(SHIPPED_MODEL, tmp_path / "broken")
    (broken / "model.pkl").write_bytes(b"x")
    body = _predict(client, child, assessment).json()
    assert body["status"] == "no_research_model" and any("SHA-256" in reason for reason in body["reasons"])


def test_research_routes_are_off_by_default_and_enforce_child_access(client: TestClient, anon_client: TestClient, make_client, monkeypatch) -> None:
    child, assessment = _visual_run(client)
    overview, predict = f"/api/screening/research/children/{child['id']}", f"/api/screening/research/children/{child['id']}/assessments/{assessment['id']}/predict"
    assert client.get(overview).status_code == 404 and client.post(predict).status_code == 404  # disabled
    monkeypatch.setattr(get_settings(), "research_demo_enabled", True)
    monkeypatch.setattr(get_settings(), "research_demo_model_dir", str(SHIPPED))
    assert anon_client.get(overview).status_code == 401 and anon_client.post(predict).status_code == 401
    for outsider in (make_client("parent"), make_client("admin"), make_client("educator")):
        assert outsider.get(overview).status_code == 404 and outsider.post(predict).status_code == 404
    educator = make_client("educator")
    client.post(f"/api/children/{child['id']}/educators", json={"educator_email": educator.user.email})
    assert educator.post(predict).json()["status"] == "available"
    # An assessment of another child cannot be scored through this child's route.
    other_child, other_assessment = _visual_run(client)
    assert client.post(f"/api/screening/research/children/{child['id']}/assessments/{other_assessment['id']}/predict").status_code == 404
    assert client.post(f"/api/screening/research/children/{child['id']}/assessments/not-a-uuid/predict").status_code == 422
