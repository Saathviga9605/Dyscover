from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.assessment import AssessmentDomain
from app.assessments.scoring import KNOWN_GAMES
from app.l10n import SUPPORTED_LANGUAGE_CODES

_LANGUAGE_PATTERN = "^[a-z]{2}$"
_VERSION_PATTERN = r"^[A-Za-z0-9._-]{1,32}$"


class HealthResponse(BaseModel):
    status: str
    version: str


class ReadinessResponse(BaseModel):
    status: str
    version: str
    database: str
    schema_revision: str | None
    lexi: str


def _validate_language(value: str) -> str:
    if value not in SUPPORTED_LANGUAGE_CODES:
        raise ValueError(f"Unsupported language {value!r}")
    return value


class ChildCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    birth_year: int | None = Field(default=None, ge=2010, le=2030)

    @field_validator("display_name")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Display name is required")
        return value


class ChildUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    birth_year: int | None = Field(default=None, ge=2010, le=2030)


class ChildResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    display_name: str
    birth_year: int | None = None
    created_at: datetime


class EducatorGrantCreate(BaseModel):
    educator_email: EmailStr

    @field_validator("educator_email")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return value.strip().lower()


class EducatorGrantResponse(BaseModel):
    child_id: UUID
    educator_id: UUID
    educator_display_name: str | None
    status: str
    created_at: datetime


class AssessmentCreate(BaseModel):
    child_id: UUID
    version: str = Field(default="stage-1", pattern=_VERSION_PATTERN)
    language: str = Field(default="en", pattern=_LANGUAGE_PATTERN)
    locale: str | None = Field(default=None, max_length=16)
    content_version: str | None = Field(default=None, pattern=_VERSION_PATTERN)

    @field_validator("language")
    @classmethod
    def _supported_language(cls, value: str) -> str:
        return _validate_language(value)


class AssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    child_id: UUID
    version: str
    language: str
    locale: str | None = None
    content_version: str | None = None
    status: str
    created_at: datetime | None = None
    started_at: datetime | None
    completed_at: datetime | None


class GameCreate(BaseModel):
    game_id: str = Field(min_length=1, max_length=80)
    game_version: str = Field(default="1.0.0", pattern=_VERSION_PATTERN)
    language: str = Field(default="en", pattern=_LANGUAGE_PATTERN)
    content_version: str = Field(default="1.0", pattern=_VERSION_PATTERN)

    @field_validator("game_id")
    @classmethod
    def _known_game(cls, value: str) -> str:
        if value not in KNOWN_GAMES:
            raise ValueError(f"Unknown game {value!r}")
        return value


class GameResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    assessment_session_id: UUID
    game_id: str
    game_version: str
    language: str
    content_version: str
    score: float | None


class TrialCreate(BaseModel):
    trial_number: int = Field(ge=1, le=500)
    stimulus: Any
    expected_response: Any = None
    actual_response: Any = None
    game_version: str = Field(default="1.0.0", pattern=_VERSION_PATTERN)
    language: str = Field(default="en", pattern=_LANGUAGE_PATTERN)
    content_version: str = Field(default="1.0", pattern=_VERSION_PATTERN)
    domain: str | None = None
    difficulty: int = Field(default=1, ge=1, le=5)
    score: float = Field(default=0, ge=0, le=1)
    attempt_count: int = Field(default=0, ge=0, le=1000)
    error_count: int = Field(default=0, ge=0, le=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    correctness: bool | None = None
    reaction_time_ms: int | None = Field(default=None, ge=0, le=3_600_000)
    hesitation_time_ms: int | None = Field(default=None, ge=0, le=3_600_000)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @field_validator("domain")
    @classmethod
    def _known_domain(cls, value: str | None) -> str | None:
        if value is not None and value not in {domain.value for domain in AssessmentDomain}:
            raise ValueError(f"Unknown domain {value!r}")
        return value


class TrialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: UUID
    game_session_id: UUID
    trial_number: int
    stimulus: Any
    expected_response: Any = None
    actual_response: Any = None
    game_version: str
    language: str
    content_version: str
    domain: str | None = None
    difficulty: int
    score: float
    attempt_count: int
    error_count: int
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_json", serialization_alias="metadata")
    correctness: bool | None
    reaction_time_ms: int | None = None
    hesitation_time_ms: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class EventCreate(BaseModel):
    event_type: str = Field(pattern=r"^[A-Z][A-Z_]{0,39}$")
    timestamp: datetime | None = None
    session_id: UUID | None = None
    game_id: str | None = Field(default=None, max_length=80)
    performance_time: float | None = None
    sequence_number: int | None = Field(default=None, ge=1, le=100_000)
    schema_version: str = Field(default="2.0", pattern=_VERSION_PATTERN)
    language: str = Field(default="en", pattern=_LANGUAGE_PATTERN)
    payload: dict = Field(default_factory=dict)

    @field_validator("event_type")
    @classmethod
    def _not_server_reserved(cls, value: str) -> str:
        if value == "CALIBRATION_COMPLETED":
            raise ValueError("CALIBRATION_COMPLETED is recorded by the gaze ingestion endpoint")
        return value


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    trial_id: UUID
    event_type: str
    timestamp: datetime | None = None
    session_id: UUID | None = None
    game_id: str | None = None
    performance_time: float | None = None
    sequence_number: int | None = None
    schema_version: str
    language: str
    payload: dict = Field(default_factory=dict)


class SummaryCreate(BaseModel):
    games: list[dict[str, Any]] = Field(default_factory=list, max_length=len(KNOWN_GAMES))
    total_trials: int = Field(default=0, ge=0, le=5000)


class SummaryResponse(SummaryCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    assessment_id: UUID
    schema_version: str
    created_at: datetime
