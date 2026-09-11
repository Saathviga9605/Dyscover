from app.speech.alignment import align_reading
from app.speech.features import extract_reading_features
from app.speech.nlp import extract_text_features
from app.speech.provider import get_speech_provider
from app.speech.schemas import ReadingTask, Transcript, TranscriptWord, ProviderState
from app.speech.service import analyze_reading
from fastapi.testclient import TestClient
from app.main import app


def test_unconfigured_provider_is_explicitly_unavailable():
    provider = get_speech_provider()
    assert provider.health_check() is ProviderState.NOT_CONFIGURED


def test_alignment_tracks_substitution_omission_and_insertion():
    result = align_reading("the cat sat", "the dog sat down")
    assert result.substitutions == 1
    assert result.insertions == 1
    assert result.matched_words == 2


def test_reading_features_require_real_duration_and_alignment():
    task = ReadingTask(task_id="fixture", expected_text="the cat sat")
    transcript = Transcript(text="the cat sat", provider="PIPELINE_TEST_ONLY", provider_version="1", words=[TranscriptWord(word="the", start_time_ms=0, end_time_ms=300), TranscriptWord(word="cat", start_time_ms=1100, end_time_ms=1400), TranscriptWord(word="sat", start_time_ms=1500, end_time_ms=1800)])
    result = analyze_reading(task, transcript, 1800)
    assert result["speech_available"] is True
    assert result["features"]["speech_words_per_minute"]["available"] is True
    assert result["features"]["speech_pause_count"]["value"] == 1


def test_missing_speech_is_not_zero_filled():
    task = ReadingTask(task_id="fixture", expected_text="the cat sat")
    result = analyze_reading(task, None, None)
    assert result["speech_available"] is False
    assert result["features"]["speech_reading_duration_ms"]["value"] is None
    assert result["features"]["text_token_count"]["available"] is False


def test_nlp_features_are_deterministic():
    result = extract_text_features("cat cat moon")
    assert result["text_token_count"]["value"] == 3
    assert result["text_unique_token_count"]["value"] == 2
    assert result["text_type_token_ratio"]["value"] == 2 / 3


def test_speech_session_stores_reference_metadata_without_audio():
    client = TestClient(app)
    with client:
        child = client.post("/api/children", json={"display_name": "Reader", "birth_year": 2018}).json()
        assessment = client.post("/api/assessments", json={"child_id": child["id"], "version": "stage-4.0"}).json()
        response = client.post("/api/speech/sessions", json={"session_id": assessment["id"], "task": {"task_id": "fixture", "expected_text": "the cat sat"}, "audio_available": False})
        assert response.status_code == 201
        assert response.json()["audio_available"] is False
        fetched = client.get(f"/api/speech/sessions/{response.json()['id']}")
        assert fetched.status_code == 200

def test_speech_api_exposes_explicit_unavailable_state():
    client = TestClient(app)
    with client:
        status_response = client.get("/api/speech/status")
        assert status_response.status_code == 200
        assert status_response.json()["state"] == "NOT_CONFIGURED"
        analysis = client.post("/api/speech/analyze", json={"task": {"task_id": "fixture", "expected_text": "the cat sat"}})
        assert analysis.status_code == 200
        assert analysis.json()["speech_available"] is False
        assert analysis.json()["provider_state"] == "UNAVAILABLE"
