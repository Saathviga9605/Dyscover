from typing import Any
from .alignment import align_reading
from .features import extract_reading_features
from .nlp import extract_text_features
from .provider import get_speech_provider
from .schemas import ProviderState, ReadingTask, SpeechFeaturesResponse, SpeechStatusResponse, Transcript


def provider_status() -> SpeechStatusResponse:
    provider = get_speech_provider()
    return SpeechStatusResponse(state=provider.health_check(), provider=provider.name, provider_version=provider.version, message="No speech provider is configured; reading analysis remains optional.")


def analyze_reading(task: ReadingTask, transcript: Transcript | None, duration_ms: int | None) -> dict[str, Any]:
    alignment = align_reading(task.expected_text, transcript.text) if transcript and transcript.transcript_available else None
    speech_features = extract_reading_features(transcript, alignment, duration_ms)
    text_features = extract_text_features(transcript.text, transcript.language) if transcript else extract_text_features("")
    return {"speech_available": transcript is not None and transcript.transcript_available, "alignment_available": alignment is not None, "provider_state": ProviderState.AVAILABLE if transcript else ProviderState.UNAVAILABLE, "task": task, "transcript_quality": transcript.quality if transcript else "UNAVAILABLE", "features": {**speech_features, **text_features}, "alignment": alignment}
