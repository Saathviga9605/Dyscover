from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ProviderState(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"
    NOT_CONFIGURED = "NOT_CONFIGURED"


class ReadingErrorType(StrEnum):
    CORRECT = "CORRECT"
    SUBSTITUTION = "SUBSTITUTION"
    OMISSION = "OMISSION"
    INSERTION = "INSERTION"
    REPETITION = "REPETITION"
    ORDER_ERROR = "ORDER_ERROR"
    UNKNOWN = "UNKNOWN"


class ReadingTask(BaseModel):
    task_id: str = Field(min_length=1)
    expected_text: str = Field(min_length=1)
    language: str = "en"
    difficulty: int = Field(default=1, ge=1, le=5)
    content_type: str = "sentence"
    version: str = "1.0"


class TranscriptWord(BaseModel):
    word: str = Field(min_length=1)
    start_time_ms: int | None = Field(default=None, ge=0)
    end_time_ms: int | None = Field(default=None, ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)


class Transcript(BaseModel):
    text: str
    language: str = "en"
    provider: str
    provider_version: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    words: list[TranscriptWord] = Field(default_factory=list)
    transcript_available: bool = True
    word_timestamps_available: bool = False
    quality: Literal["OK", "WARNING", "INVALID", "UNAVAILABLE"] = "OK"


class AlignmentItem(BaseModel):
    expected: str | None = None
    actual: str | None = None
    error_type: ReadingErrorType


class ReadingAlignment(BaseModel):
    expected_text: str
    transcript_text: str
    items: list[AlignmentItem]
    matched_words: int
    substitutions: int
    omissions: int
    insertions: int
    repetitions: int
    order_differences: int
    quality: Literal["OK", "WARNING", "INVALID", "UNAVAILABLE"] = "OK"


class SpeechSessionCreate(BaseModel):
    session_id: UUID
    trial_id: UUID | None = None
    task: ReadingTask
    language: str = "en"
    locale: str | None = None
    provider: str = "unconfigured"
    provider_version: str = "unknown"
    audio_available: bool = False
    duration_ms: int | None = Field(default=None, ge=0)


class SpeechSessionResponse(BaseModel):
    id: UUID
    session_id: UUID
    trial_id: UUID | None = None
    task: ReadingTask
    language: str
    locale: str
    provider: str
    provider_version: str
    audio_available: bool
    duration_ms: int | None = None
    created_at: datetime


class SpeechFeaturesResponse(BaseModel):
    speech_available: bool
    alignment_available: bool
    provider_state: ProviderState
    task: ReadingTask
    transcript_quality: str
    features: dict[str, dict[str, Any]]
    alignment: ReadingAlignment | None = None


class SpeechStatusResponse(BaseModel):
    state: ProviderState
    provider: str
    provider_version: str
    message: str
