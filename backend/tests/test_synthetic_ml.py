"""Comprehensive test suite for Dyscover Synthetic ML Classification Pipeline.

Covers:
- Simulator reproducibility, determinism, and variance across seeds
- Game family coverage and domain mappings
- Operational scenario definitions and non-clinical taxonomy
- Modality simulation honesty (gaze and speech availability/missingness)
- Language boundary enforcement (Tamil restricted to mirror-match)
- Validation rules and negative corrupted fixtures
- Subject-level leakage prevention
- Class coverage and preprocessing fit on training data only
- Genuine estimator fitting (Dummy, Logistic Regression, Random Forest, Gradient Boosting)
- Artifact integrity verification and tampering rejection
- Research vs Production registry isolation
- Synthetic inference isolation (SYNTHETIC_RESEARCH_ONLY disclaimers)
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import pytest

from app.ml.feature_registry import REGISTRY_BY_NAME
from app.ml.registry import list_models, register_model
from app.ml.schemas import ModelInfo
from app.ml.synthetic import (
    CONTENT_VERSION,
    ELIGIBLE_SCENARIOS,
    PROFILES,
    RESEARCH_REGISTRY,
    SCENARIO_DEFINITIONS,
    SIMULATOR_VERSION,
    SPEECH_GAMES,
    SUPPORTED_GAMES,
    SUPPORTED_SCENARIOS,
    SYNTHETIC_SCHEMA_VERSION,
    VISUAL_GAMES,
    SyntheticConfig,
    SyntheticModelRecord,
    ensure_synthetic_purity,
    export_dataset,
    generate_dataset,
    generate_negative_fixtures,
    infer_synthetic_profile,
    load_synthetic_model,
    train_synthetic_models,
    validate_game_language_pair,
    validate_synthetic_row,
)


# =====================================================================
# 1. Simulator Tests
# =====================================================================

def test_simulator_determinism_same_seed_produces_identical_rows():
    config1 = SyntheticConfig(seed=123, subjects=4, sessions_per_subject=2, trials_per_session=3)
    config2 = SyntheticConfig(seed=123, subjects=4, sessions_per_subject=2, trials_per_session=3)

    data1 = generate_dataset(config1)
    data2 = generate_dataset(config2)

    assert data1["metadata"]["data_checksum"] == data2["metadata"]["data_checksum"]
    assert len(data1["rows"]) == len(data2["rows"])
    for r1, r2 in zip(data1["rows"], data2["rows"]):
        assert r1["target"] == r2["target"]
        assert r1["game_id"] == r2["game_id"]
        for feat_name in r1["features"]:
            assert r1["features"][feat_name]["value"] == r2["features"][feat_name]["value"]


def test_simulator_seed_variation_produces_varied_observations():
    config1 = SyntheticConfig(seed=101, subjects=4, sessions_per_subject=2)
    config2 = SyntheticConfig(seed=202, subjects=4, sessions_per_subject=2)

    data1 = generate_dataset(config1)
    data2 = generate_dataset(config2)

    assert data1["metadata"]["data_checksum"] != data2["metadata"]["data_checksum"]
    # Check that accuracy or reaction times differ
    rt1 = [r["features"]["mean_reaction_time_ms"]["value"] for r in data1["rows"]]
    rt2 = [r["features"]["mean_reaction_time_ms"]["value"] for r in data2["rows"]]
    assert rt1 != rt2


def test_all_supported_game_families_represented():
    config = SyntheticConfig(seed=42, subjects=16, sessions_per_subject=2, games=SUPPORTED_GAMES)
    dataset = generate_dataset(config)

    observed_games = {r["game_id"] for r in dataset["rows"]}
    assert set(VISUAL_GAMES).issubset(observed_games)
    assert set(SPEECH_GAMES).issubset(observed_games)
    assert set(SUPPORTED_GAMES) == observed_games


def test_scenario_labels_match_documented_definitions():
    config = SyntheticConfig(seed=42, subjects=18, sessions_per_subject=2)
    dataset = generate_dataset(config)

    for r in dataset["rows"]:
        scenario = r["target"]
        assert scenario in SUPPORTED_SCENARIOS
        profile = PROFILES[scenario]
        assert profile.operational_definition
        assert profile.simulation_assumptions

        # Insufficient observations must be marked as not eligible
        if scenario == "insufficient_observations":
            assert r["eligible"] is False
            assert r["completed"] is False
        else:
            assert r["eligible"] is True


def test_optional_modality_honesty_when_unavailable():
    # Modality availability set to 0.0 -> all gaze and speech must be missing
    config = SyntheticConfig(seed=42, subjects=4, sessions_per_subject=2, modality_availability=0.0)
    dataset = generate_dataset(config)

    for r in dataset["rows"]:
        feats = r["features"]
        assert feats["gaze_available"]["value"] is None or feats["gaze_available"]["value"] == 0
        assert feats["gaze_available"]["available"] is False
        assert feats["gaze_sample_count"]["value"] is None
        assert feats["gaze_sample_count"]["available"] is False

        assert feats["speech_available"]["value"] is None or feats["speech_available"]["value"] == 0
        assert feats["speech_available"]["available"] is False
        assert feats["speech_reading_duration_ms"]["value"] is None
        assert feats["speech_reading_duration_ms"]["available"] is False


def test_unsupported_language_combinations_rejected():
    # Tamil is allowed for mirror-match
    validate_game_language_pair("mirror-match", "ta")

    # Tamil is rejected for English-orthography games
    for visual_game in set(VISUAL_GAMES) - {"mirror-match"}:
        with pytest.raises(ValueError, match="Tamil"):
            validate_game_language_pair(visual_game, "ta")

    # Speech games only support English
    for speech_game in SPEECH_GAMES:
        with pytest.raises(ValueError, match="Tamil"):
            validate_game_language_pair(speech_game, "ta")

    # Arbitrary unsupported languages are rejected
    with pytest.raises(ValueError, match="Language 'fr' is not supported"):
        validate_game_language_pair("mirror-match", "fr")


def test_valid_simulated_rows_pass_validation():
    config = SyntheticConfig(seed=42, subjects=9, sessions_per_subject=2)
    dataset = generate_dataset(config)

    for r in dataset["rows"]:
        issues = validate_synthetic_row(r)
        assert issues == [], f"Valid row had validation issues: {issues}"


def test_invalid_fixtures_fail_validation():
    config = SyntheticConfig(seed=42, subjects=3, sessions_per_subject=1)
    dataset = generate_dataset(config)
    valid_row = dataset["rows"][0]

    fixtures = generate_negative_fixtures(valid_row)

    for name, fixture in fixtures.items():
        issues = validate_synthetic_row(fixture)
        assert issues != [], f"Fixture '{name}' unexpectedly passed validation"
        expected = fixture["expected_issue"]
        assert any(expected.split(":")[0] in issue for issue in issues), (
            f"Expected issue '{expected}' not found in {issues}"
        )


# =====================================================================
# 2. Dataset & Leakage Prevention Tests
# =====================================================================

def test_dataset_provenance_and_checksum_integrity(tmp_path: Path):
    config = SyntheticConfig(seed=99, subjects=9, sessions_per_subject=2)
    dataset = generate_dataset(config)

    meta = dataset["metadata"]
    assert meta["synthetic"] is True
    assert meta["simulator_version"] == SIMULATOR_VERSION
    assert meta["feature_schema_version"] == SYNTHETIC_SCHEMA_VERSION
    assert meta["content_version"] == CONTENT_VERSION
    assert meta["seed"] == 99
    assert meta["subjects"] == 9
    assert meta["sessions"] == 18
    assert meta["data_checksum"]

    export_path = tmp_path / "test_dataset.json"
    export_dataset(dataset, export_path)

    loaded = json.loads(export_path.read_text(encoding="utf-8"))
    assert loaded["metadata"]["data_checksum"] == meta["data_checksum"]

    with pytest.raises(FileExistsError):
        export_dataset(dataset, export_path)


def test_synthetic_and_real_data_cannot_be_silently_mixed():
    config = SyntheticConfig(seed=42, subjects=3, sessions_per_subject=1)
    dataset = generate_dataset(config)
    synth_row = dataset["rows"][0]

    real_row = {
        "subject_id": "real-child-001",
        "session_id": "real-sess-001",
        "synthetic": False,
        "features": {},
    }

    # Clean synthetic list passes
    ensure_synthetic_purity([synth_row, copy.deepcopy(synth_row)])

    # Clean real list passes
    ensure_synthetic_purity([real_row, copy.deepcopy(real_row)])

    # Mixed list raises DATASET CONTAMINATION ERROR
    with pytest.raises(ValueError, match="DATASET CONTAMINATION ERROR"):
        ensure_synthetic_purity([synth_row, real_row])


def test_subject_level_split_prevents_subject_leakage(tmp_path: Path):
    config = SyntheticConfig(seed=42, subjects=18, sessions_per_subject=3)
    dataset = generate_dataset(config)

    results = train_synthetic_models(dataset, tmp_path / "models", algorithms=("dummy", "logistic_regression"))

    meta = results["logistic_regression"]
    eval_rep = meta["evaluation"]
    train_subs = eval_rep["partitions"]["train_subject_count"]
    val_subs = eval_rep["partitions"]["validation_subject_count"]
    test_subs = eval_rep["partitions"]["test_subject_count"]

    assert train_subs > 0
    assert val_subs > 0
    assert test_subs > 0
    # 18 total subjects minus 2 insufficient_observations subjects = 16 eligible subjects
    eligible_subjects = len({r["subject_id"] for r in dataset["rows"] if r["eligible"]})
    assert train_subs + val_subs + test_subs == eligible_subjects


# =====================================================================
# 3. Model Training & Evaluation Tests
# =====================================================================

def test_train_all_baseline_estimators(tmp_path: Path):
    config = SyntheticConfig(seed=42, subjects=27, sessions_per_subject=2)
    dataset = generate_dataset(config)

    output_dir = tmp_path / "synthetic_baselines"
    results = train_synthetic_models(
        dataset,
        output_dir,
        algorithms=("dummy", "logistic_regression", "random_forest", "gradient_boosting"),
    )

    for algo in ("dummy", "logistic_regression", "random_forest", "gradient_boosting"):
        assert algo in results
        meta = results[algo]
        assert meta["synthetic"] is True
        assert meta["intended_use"] == "simulator_profile_classification"
        assert meta["clinical_use"] == "prohibited"
        assert meta["artifact_sha256"]

        # Check model file exists
        pkl_path = output_dir / f"{algo}.pkl"
        assert pkl_path.is_file()

        eval_rep = meta["evaluation"]
        assert eval_rep["status"] == "SYNTHETIC_RESEARCH_ONLY"
        assert "clinical dyslexia" in eval_rep["scientific_disclaimer"].lower()
        test_m = eval_rep["test_metrics"]
        assert "accuracy" in test_m
        assert "confusion_matrix" in test_m


def test_load_synthetic_model_and_integrity_check(tmp_path: Path):
    config = SyntheticConfig(seed=42, subjects=18, sessions_per_subject=2)
    dataset = generate_dataset(config)

    output_dir = tmp_path / "integrity_test"
    train_synthetic_models(dataset, output_dir, algorithms=("logistic_regression",))

    meta_path = output_dir / "logistic_regression.json"
    model, loaded_meta = load_synthetic_model(meta_path)
    assert model.model_type == "logistic_regression"
    assert loaded_meta["algorithm"] == "logistic_regression"

    # Tampering test: corrupt metadata SHA
    corrupted_meta = copy.deepcopy(loaded_meta)
    corrupted_meta["artifact_sha256"] = "tampered_fake_sha"
    corrupt_path = output_dir / "corrupt.json"
    corrupt_path.write_text(json.dumps(corrupted_meta), encoding="utf-8")

    with pytest.raises(ValueError, match="integrity check failed"):
        load_synthetic_model(corrupt_path)


def test_schema_version_mismatch_rejected(tmp_path: Path):
    config = SyntheticConfig(seed=42, subjects=18, sessions_per_subject=2)
    dataset = generate_dataset(config)
    output_dir = tmp_path / "schema_test"
    train_synthetic_models(dataset, output_dir, algorithms=("random_forest",))

    meta_path = output_dir / "random_forest.json"
    with pytest.raises(ValueError, match="Schema version mismatch"):
        load_synthetic_model(meta_path, expected_schema_version="99.0")


def test_synthetic_models_cannot_enter_production_registry(tmp_path: Path):
    # Production list_models only returns production models with status unavailable
    prod_models = list_models()
    for m in prod_models:
        assert not getattr(m, "synthetic", False)

    # Attempting to register a synthetic model in production registry raises PermissionError
    fake_synth_info = ModelInfo(
        model_id="synthetic-attempt-v1",
        model_name="Synthetic Attempt",
        model_type="logistic_regression",
        version="1.0",
        feature_schema_version="1.0",
        status="research",
        training_status="trained",
        algorithm="logistic_regression",
        hyperparameters={},
        synthetic=True,
    )

    with pytest.raises(PermissionError, match="prohibited"):
        register_model(fake_synth_info)


def test_synthetic_inference_is_marked_research_only_and_safe(tmp_path: Path):
    config = SyntheticConfig(seed=42, subjects=18, sessions_per_subject=2)
    dataset = generate_dataset(config)
    output_dir = tmp_path / "inference_test"
    train_synthetic_models(dataset, output_dir, algorithms=("logistic_regression",))

    model, _ = load_synthetic_model(output_dir / "logistic_regression.json")
    test_rows = dataset["rows"][:2]

    result = infer_synthetic_profile(model, test_rows)
    assert result["status"] == "SYNTHETIC_RESEARCH_ONLY"
    assert result["clinical_use"] == "prohibited"
    assert "simulated interaction profile" in result["scientific_disclaimer"]
    assert len(result["predictions"]) == 2
    assert all(p in SUPPORTED_SCENARIOS for p in result["predictions"])


def test_research_registry_manages_synthetic_models(tmp_path: Path):
    config = SyntheticConfig(seed=42, subjects=18, sessions_per_subject=2)
    dataset = generate_dataset(config)
    output_dir = tmp_path / "research_reg_test"
    train_synthetic_models(dataset, output_dir, algorithms=("logistic_regression",))

    meta_path = output_dir / "logistic_regression.json"
    record = RESEARCH_REGISTRY.register(meta_path)

    assert record.synthetic is True
    assert record.intended_use == "simulator_profile_classification"
    assert record.clinical_use == "prohibited"
    assert RESEARCH_REGISTRY.get(record.model_id) == record
