import json
import sys
import types
from pathlib import Path

import pytest

from app.ml.training import ExperimentConfig, infer_research_model, load_research_model, train_research_model
from app.speech.provider import FasterWhisperProvider
from app.speech.schemas import ProviderState


def _rows():
    return [
        {"subject_id": f"subject-{index}", "session_id": f"session-{index}", "features": {"overall_accuracy": .2 + index * .05}}
        for index in range(10)
    ]


def test_research_artifact_round_trip_and_schema_validation(tmp_path: Path):
    rows = _rows()
    labels = [index % 2 for index in range(len(rows))]
    metadata = train_research_model(rows, labels, ExperimentConfig("fixture", "test-only"), tmp_path / "fixture")
    model, loaded = load_research_model(tmp_path / "fixture.json")

    assert metadata["training_status"] == "trained"
    assert loaded["artifact_sha256"]
    result = infer_research_model(model, [{"features": {"overall_accuracy": .6}}])
    assert result["predictions"] in ([0], [1])
    with pytest.raises(ValueError, match="schema version"):
        infer_research_model(model, [{"features": {"overall_accuracy": .6}}], "9.0")


def test_research_artifact_rejects_tampering(tmp_path: Path):
    rows = _rows()
    train_research_model(rows, [index % 2 for index in range(len(rows))], ExperimentConfig("fixture", "test-only"), tmp_path / "fixture")
    metadata_path = tmp_path / "fixture.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["artifact_sha256"] = "invalid"
    metadata_path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="integrity"):
        load_research_model(metadata_path)


def test_faster_whisper_adapter_invokes_real_provider_without_persisting_audio(tmp_path: Path, monkeypatch):
    class Word:
        word = "cat"
        start = 0.0
        end = 0.4

    class Segment:
        text = " cat"
        words = [Word()]

    class Model:
        model_size_or_path = "fixture-model"

        def transcribe(self, path, language):
            assert Path(path).is_file()
            assert language == "en"
            return iter([Segment()]), types.SimpleNamespace(language=language)

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=lambda *args, **kwargs: Model()))
    monkeypatch.setenv("DYSCOVER_ASR_PROVIDER", "faster-whisper")
    audio = tmp_path / "fixture.wav"
    audio.write_bytes(b"test audio")
    provider = FasterWhisperProvider()
    transcript = provider.transcribe(str(audio), "en", consent_given=True)

    assert transcript.text == "cat"
    assert transcript.provider == "faster-whisper"
    assert transcript.words[0].word == "cat"


def test_faster_whisper_adapter_rejects_unsupported_locale_and_missing_consent():
    provider = FasterWhisperProvider()
    with pytest.raises(ValueError, match="unsupported"):
        provider.transcribe("missing.wav", "fr", consent_given=True)
    with pytest.raises(PermissionError, match="consent"):
        provider.transcribe("missing.wav", "ta", consent_given=False)


def test_faster_whisper_health_check_reports_unavailable_model(monkeypatch):
    monkeypatch.setenv("DYSCOVER_ASR_MODEL_PATH", "missing-model")
    monkeypatch.setenv("DYSCOVER_ASR_ALLOW_MODEL_LOAD", "true")
    provider = FasterWhisperProvider()
    assert provider.health_check() is ProviderState.UNAVAILABLE
