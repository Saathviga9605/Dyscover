from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

GAZE_SCHEMA_VERSION = "1.0"


class GazeSampleCreate(BaseModel):
    """One gaze-estimate sample in viewport coordinates (screen px).

    ``timestamp_ms`` is an epoch-millisecond clock value produced by the
    provider.  Media streams are never transmitted; only coordinate
    estimates and explicit quality flags arrive at the API.
    """

    x: float
    y: float
    timestamp_ms: float = Field(ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)
    quality: Literal["tracking", "degraded", "out_of_order", "unavailable"] = "tracking"
    viewport_width: int | None = Field(default=None, gt=0)
    viewport_height: int | None = Field(default=None, gt=0)


class FixationCreate(BaseModel):
    """A deterministic fixation derived client-side from gaze samples."""

    start_timestamp_ms: float = Field(ge=0)
    end_timestamp_ms: float = Field(ge=0)
    duration_ms: int = Field(ge=0)
    x: float
    y: float
    target_type: str | None = Field(default=None, max_length=40)
    target_id: str | None = Field(default=None, max_length=120)

    @field_validator("duration_ms")
    @classmethod
    def duration_within_window(cls, value: int, info: object) -> int:
        start = info.data.get("start_timestamp_ms")
        end = info.data.get("end_timestamp_ms")
        if start is not None and end is not None and (end - start) < value:
            raise ValueError("duration_ms exceeds the fixation time window")
        return value


class GazeTrialBatchCreate(BaseModel):
    """Per-trial batch of gaze samples and fixations for one provider run."""

    samples: list[GazeSampleCreate] = Field(default_factory=list, max_length=20_000)
    fixations: list[FixationCreate] = Field(default_factory=list, max_length=2_000)
    provider: str = Field(default="webgazer", max_length=80)
    provider_version: str = Field(default="unknown", max_length=40)
    quality: Literal["tracking", "degraded", "out_of_order", "unavailable"] = "tracking"
    schema_version: str = GAZE_SCHEMA_VERSION


class GazeBatchResponse(BaseModel):
    trial_id: UUID
    samples_created: int
    fixations_created: int
    samples_rejected: int
    fixations_rejected: int
    quality: str


class GazeTrialSummary(BaseModel):
    trial_id: UUID
    sample_count: int
    fixation_count: int
    quality: str | None = None
    fixations: list[dict] = Field(default_factory=list)


class GazeStatusResponse(BaseModel):
    modality: str = "gaze"
    available: bool = True
    sample_schema_version: str = GAZE_SCHEMA_VERSION
    message: str = "Gaze observations are accepted per trial; raw media is never stored."
    raw_media_stored: bool = False