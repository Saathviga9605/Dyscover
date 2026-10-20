from typing import Any

from pydantic import BaseModel, Field, field_validator

from .schemas import ReadingTask, Transcript

MAX_FEATURE_KEYS = 200


class ReadingAnalysisRequest(BaseModel):
    task: ReadingTask
    transcript: Transcript | None = None
    duration_ms: int | None = Field(default=None, ge=0, le=600_000)


class SpeechFeaturesStoreRequest(BaseModel):
    features: dict[str, Any]

    @field_validator("features")
    @classmethod
    def _bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > MAX_FEATURE_KEYS:
            raise ValueError(f"At most {MAX_FEATURE_KEYS} features may be stored per speech session")
        if any(len(key) > 80 for key in value):
            raise ValueError("Feature names must be at most 80 characters")
        return value
