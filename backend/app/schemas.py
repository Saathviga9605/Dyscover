from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from typing import Any


class HealthResponse(BaseModel):
    status: str
    version: str


class ChildCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    birth_year: int | None = Field(default=None, ge=2010, le=2030)


class ChildResponse(ChildCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime


class AssessmentCreate(BaseModel):
    child_id: UUID
    version: str = "stage-1"
    language: str = "en"
    locale: str | None = None
    content_version: str | None = None


class AssessmentResponse(AssessmentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: str
    started_at: datetime | None
    completed_at: datetime | None


class GameCreate(BaseModel):
    game_id: str = Field(min_length=1, max_length=80)
    game_version: str = "1.0.0"
    language: str = "en"
    content_version: str = "1.0"


class GameResponse(GameCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    assessment_session_id: UUID
    score: float | None
    game_version: str


class TrialCreate(BaseModel):
    trial_number: int = Field(ge=1)
    stimulus: Any
    expected_response: Any = None
    actual_response: Any = None
    game_version: str = "1.0.0"
    language: str = "en"
    content_version: str = "1.0"
    domain: str | None = None
    difficulty: int = Field(default=1, ge=1, le=5)
    score: float = Field(default=0, ge=0)
    attempt_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    correctness: bool | None = None
    reaction_time_ms: int | None = Field(default=None, ge=0)
    hesitation_time_ms: int | None = Field(default=None, ge=0)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class TrialResponse(TrialCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    game_session_id: UUID
    actual_response: Any
    correctness: bool | None
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_json", serialization_alias="metadata")


class EventCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=40)
    timestamp: datetime | None = None
    session_id: UUID | None = None
    game_id: str | None = None
    performance_time: float | None = None
    sequence_number: int | None = Field(default=None, ge=1)
    schema_version: str = "2.0"
    language: str = "en"
    payload: dict = Field(default_factory=dict)


class EventResponse(EventCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    trial_id: UUID


class SummaryCreate(BaseModel):
    games: list[dict[str, Any]] = Field(default_factory=list)
    total_trials: int = Field(default=0, ge=0)


class SummaryResponse(SummaryCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    assessment_id: UUID
    schema_version: str
    created_at: datetime
