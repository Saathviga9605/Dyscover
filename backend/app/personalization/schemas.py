"""Pydantic schemas for personalization API responses.

Schemas are intentionally thin: they exist to give OpenAPI a valid
``response_model`` and to document contracts.  The service layer
builds dicts directly; these schemas validate structure only.
"""

from pydantic import BaseModel


class EvidenceReport(BaseModel):
    state: str
    trial_count: int
    valid_trial_count: int
    completed_trial_count: int
    incomplete_trial_count: int
    minimum_valid_trials: int


class DomainSkillResponse(BaseModel):
    domain: str
    label: str
    evidence_state: str
    accuracy: float | None = None
    mean_reaction_time_ms: float | None = None
    trial_count: int = 0
    valid_trial_count: int = 0
    completed_trial_count: int = 0
    incomplete_trial_count: int = 0
    correct_count: int = 0
    error_count: int = 0
    games: list[str] = []
    category: str = ""
    confidence: str = "low"
    reason: str | None = None
    observations: list[str] = []


class SkillProfileResponse(BaseModel):
    child_id: str
    engine_version: str
    schema_version: str
    config_summary: dict = {}
    mode: str
    skills: list[DomainSkillResponse]


class DifficultyDecisionResponse(BaseModel):
    level: int
    previous_level: int | None
    default: int
    window_size: int
    reason: str
    changed: bool


class RecommendationResponse(BaseModel):
    game_id: str | None = None
    target_domain: str | None = None
    target_domain_label: str | None = None
    priority: int
    reason: str
    category: str
    suggested_difficulty: int | None = None
    kind: str = "game_activity"


class RecommendationsResponse(BaseModel):
    child_id: str
    engine_version: str
    mode: str
    recommendations: list[RecommendationResponse]


class ProgressPointResponse(BaseModel):
    assessment_id: str
    completed_at: str | None
    domains: dict[str, float]


class DomainDelta(BaseModel):
    earliest_accuracy: float
    latest_accuracy: float
    delta: float


class ProgressTrendComparison(BaseModel):
    earliest_assessment_id: str
    latest_assessment_id: str
    domains: dict[str, DomainDelta]


class ProgressResponse(BaseModel):
    child_id: str
    engine_version: str
    mode: str
    points: list[ProgressPointResponse]
    comparison: ProgressTrendComparison | None = None
    note: str | None = None