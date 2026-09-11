from statistics import mean, median, pvariance
from typing import Any

from app.ml.feature_registry import REGISTRY_BY_NAME
from .schemas import ReadingAlignment, Transcript


def feature(name: str, value: float | int | None, unit: str, source: str, domain: str, available: bool, language: str, provider: str) -> dict[str, Any]:
    definition = REGISTRY_BY_NAME.get(name)
    return {"name": name, "value": value, "unit": unit, "source": source, "domain": domain, "available": available, "status": "available" if available else "missing", "modality": definition.modality if definition else "speech", "language": language, "provider": provider, "provider_version": "unknown", "feature_version": "1.0", "aggregation": definition.aggregation if definition else "derived"}


def extract_reading_features(transcript: Transcript | None, alignment: ReadingAlignment | None, duration_ms: int | None, pause_threshold_ms: int = 700) -> dict[str, dict[str, Any]]:
    language = transcript.language if transcript else "unknown"
    provider = transcript.provider if transcript else "unavailable"
    words = transcript.words if transcript else []
    timed_words = [word for word in words if word.start_time_ms is not None and word.end_time_ms is not None]
    duration_available = duration_ms is not None and duration_ms >= 0
    expected_count = len(alignment.items) if alignment else 0
    features = {
        "speech_reading_duration_ms": feature("speech_reading_duration_ms", duration_ms, "milliseconds", provider, "fluency", duration_available, language, provider),
        "speech_words_per_minute": feature("speech_words_per_minute", len(words) / (duration_ms / 60000) if duration_available and duration_ms > 0 and words else None, "words_per_minute", provider, "fluency", duration_available and duration_ms > 0 and bool(words), language, provider),
        "speech_substitution_count": feature("speech_substitution_count", alignment.substitutions if alignment else None, "count", "alignment", "reading_errors", alignment is not None, language, provider),
        "speech_omission_count": feature("speech_omission_count", alignment.omissions if alignment else None, "count", "alignment", "reading_errors", alignment is not None, language, provider),
        "speech_insertion_count": feature("speech_insertion_count", alignment.insertions if alignment else None, "count", "alignment", "reading_errors", alignment is not None, language, provider),
        "speech_repetition_count": feature("speech_repetition_count", alignment.repetitions if alignment else None, "count", "alignment", "reading_errors", alignment is not None, language, provider),
        "speech_error_rate": feature("speech_error_rate", (alignment.substitutions + alignment.omissions + alignment.insertions) / expected_count if alignment and expected_count else None, "proportion", "alignment", "reading_errors", alignment is not None and expected_count > 0, language, provider),
        "speech_pause_count": feature("speech_pause_count", sum(max(0, current.start_time_ms - previous.end_time_ms) >= pause_threshold_ms for previous, current in zip(timed_words, timed_words[1:])), "count", provider, "pauses", bool(timed_words) and len(timed_words) > 1, language, provider),
        "speech_mean_pause_duration_ms": feature("speech_mean_pause_duration_ms", mean(gaps) if (gaps := [current.start_time_ms - previous.end_time_ms for previous, current in zip(timed_words, timed_words[1:]) if current.start_time_ms - previous.end_time_ms >= pause_threshold_ms]) else None, "milliseconds", provider, "pauses", bool(timed_words) and len(timed_words) > 1, language, provider),
        "speech_median_pause_duration_ms": feature("speech_median_pause_duration_ms", median(gaps) if (gaps := [current.start_time_ms - previous.end_time_ms for previous, current in zip(timed_words, timed_words[1:]) if current.start_time_ms - previous.end_time_ms >= pause_threshold_ms]) else None, "milliseconds", provider, "pauses", bool(timed_words) and len(timed_words) > 1, language, provider),
        "speech_pause_variability_ms2": feature("speech_pause_variability_ms2", pvariance(gaps) if (gaps := [current.start_time_ms - previous.end_time_ms for previous, current in zip(timed_words, timed_words[1:]) if current.start_time_ms - previous.end_time_ms >= pause_threshold_ms]) and len(gaps) > 1 else None, "milliseconds_squared", provider, "pauses", bool(timed_words) and len(timed_words) > 2, language, provider),
    }
    return features
