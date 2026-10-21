"""Tests for experiment configuration and registry."""

from __future__ import annotations

import pytest

# Optional offline stack (requirements-speech-ml.txt); skipped, not failed, without it.
for _name in ("torch", "soundfile", "transformers", "jiwer"):
    pytest.importorskip(_name, reason="optional speech-ML stack not installed: pip install -r requirements-speech-ml.txt")

import json
import tempfile
from pathlib import Path

import pytest

from app.ml.speech.experiment import (
    SpeechExperimentConfig,
    SpeechModelInfo,
    SpeechModelRegistry,
    create_experiment_config,
    generate_experiment_report,
)
from app.ml.speech.training import WhisperFineTuneConfig
from app.ml.speech.evaluation import EvaluationConfig


class TestSpeechExperimentConfig:
    def test_create_config(self):
        config = create_experiment_config(
            experiment_name="test-exp",
            base_model="openai/whisper-tiny",
            dataset_manifest="data/manifest.jsonl",
            language="en",
        )
        assert config.experiment_name == "test-exp"
        assert config.base_model == "openai/whisper-tiny"
        assert config.language == "en"
        assert config.training_config is not None
        assert config.evaluation_config is not None
        assert config.output_dir != ""

    def test_config_serialization(self):
        config = create_experiment_config(
            experiment_name="test-exp",
            base_model="openai/whisper-tiny",
        )
        data = config.to_dict()
        assert data["experiment_name"] == "test-exp"
        assert "training_config" in data
        assert "evaluation_config" in data

        restored = SpeechExperimentConfig.from_dict(data)
        assert restored.experiment_name == config.experiment_name
        assert restored.base_model == config.base_model

    def test_save_load(self):
        config = create_experiment_config(experiment_name="test-save")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            config.save(path)
            assert path.exists()

            loaded = SpeechExperimentConfig.load(path)
            assert loaded.experiment_id == config.experiment_id
            assert loaded.experiment_name == config.experiment_name


class TestSpeechModelInfo:
    def test_model_info_creation(self):
        info = SpeechModelInfo(
            model_id="test-model-v1",
            experiment_id="exp-123",
            base_model="openai/whisper-tiny",
            base_model_revision="main",
            language="en",
            dataset_name="custom",
            dataset_version="1.0",
            dataset_manifest_hash="abc123",
            training_config={"epochs": 3},
        )
        assert info.model_id == "test-model-v1"
        assert info.status == "trained"

    def test_serialization(self):
        info = SpeechModelInfo(
            model_id="test",
            experiment_id="exp",
            base_model="openai/whisper-tiny",
            base_model_revision="main",
            language="en",
            dataset_name="test",
            dataset_version="1.0",
            dataset_manifest_hash="hash",
            training_config={},
        )
        data = info.to_dict()
        restored = SpeechModelInfo.from_dict(data)
        assert restored.model_id == info.model_id
        assert restored.base_model == info.base_model


class TestSpeechModelRegistry:
    def test_register_and_get(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = SpeechModelRegistry(Path(tmpdir))

            info = SpeechModelInfo(
                model_id="model-1",
                experiment_id="exp-1",
                base_model="openai/whisper-tiny",
                base_model_revision="main",
                language="en",
                dataset_name="test",
                dataset_version="1.0",
                dataset_manifest_hash="hash",
                training_config={},
            )
            registered = registry.register(info)
            assert registered.model_id == "model-1"

            retrieved = registry.get("model-1")
            assert retrieved is not None
            assert retrieved.model_id == "model-1"

    def test_list_models(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = SpeechModelRegistry(Path(tmpdir))

            for i in range(3):
                info = SpeechModelInfo(
                    model_id=f"model-{i}",
                    experiment_id=f"exp-{i}",
                    base_model="openai/whisper-tiny",
                    base_model_revision="main",
                    language="en",
                    dataset_name="test",
                    dataset_version="1.0",
                    dataset_manifest_hash="hash",
                    training_config={},
                    status="trained" if i < 2 else "deprecated",
                )
                registry.register(info)

            all_models = registry.list_models()
            assert len(all_models) == 3

            trained = registry.list_models(status="trained")
            assert len(trained) == 2

    def test_unregister(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = SpeechModelRegistry(Path(tmpdir))

            info = SpeechModelInfo(
                model_id="model-1",
                experiment_id="exp-1",
                base_model="openai/whisper-tiny",
                base_model_revision="main",
                language="en",
                dataset_name="test",
                dataset_version="1.0",
                dataset_manifest_hash="hash",
                training_config={},
            )
            registry.register(info)
            assert registry.get("model-1") is not None

            result = registry.unregister("model-1")
            assert result is True
            assert registry.get("model-1") is None


class TestGenerateExperimentReport:
    def test_report_generation(self):
        config = create_experiment_config(
            experiment_name="test-report",
            base_model="openai/whisper-tiny",
        )
        config.training_status = "completed"
        config.model_checkpoint_path = "outputs/model"

        report = generate_experiment_report(config)
        assert "test-report" in report
        assert "openai/whisper-tiny" in report
        assert "Training Configuration" in report
        assert "Evaluation Configuration" in report
        assert "Environment" in report

    def test_report_with_evaluation(self):
        from app.ml.speech.evaluation import EvaluationResult, SamplePrediction

        config = create_experiment_config(experiment_name="test-eval")
        eval_result = EvaluationResult(
            model_name="openai/whisper-tiny",
            model_path="openai/whisper-tiny",
            dataset_manifest="test.jsonl",
            dataset_hash="abc",
            num_samples=10,
            wer=0.15,
            cer=0.05,
            wer_median=0.12,
            cer_median=0.04,
            samples=[],
            evaluation_config={},
        )

        report = generate_experiment_report(config, eval_result)
        assert "**WER:** 0.1500" in report
        assert "**CER:** 0.0500" in report