from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FeatureValue(BaseModel):
    name: str
    value: float | int | str | None
    unit: str
    source: str
    domain: str
    available: bool
    extraction_version: str = "1.0"
    calculation_version: str = "1.0"
    modality: Literal["behavior", "gaze", "speech", "text"] = "behavior"
    status: Literal["available", "missing", "invalid", "not_applicable"] = "available"


class FeatureVectorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    session_id: UUID
    feature_schema_version: str
    feature_extractor_version: str
    features: dict[str, FeatureValue]
    quality: dict[str, Any]
    created_at: datetime


class DatasetRow(BaseModel):
    subject_id: str
    session_id: str
    features: dict[str, float | None]
    target: str | float | int | None = None


class DatasetSplit(BaseModel):
    train: list[DatasetRow]
    validation: list[DatasetRow]
    test: list[DatasetRow]
    strategy: str
    random_seed: int


class ModelInfo(BaseModel):
    model_id: str
    model_name: str
    model_type: Literal["logistic_regression", "random_forest", "gradient_boosting"]
    version: str
    feature_schema_version: str
    training_dataset_version: str | None = None
    status: Literal["unavailable", "trained", "validated", "deprecated", "failed", "research", "experimental"]
    training_status: Literal["unavailable", "trained", "validated", "failed"] = "unavailable"
    algorithm: str | None = None
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    supported_modalities: list[str] = Field(default_factory=lambda: ["behavior"])
    metrics: dict[str, float] = Field(default_factory=dict)


class PredictionResponse(BaseModel):
    status: Literal["unavailable", "available"]
    mode: Literal["DEMO", "OBSERVATION_ONLY", "RESEARCH", "MODEL_INFERENCE", "UNAVAILABLE"]
    model_state: Literal["unavailable", "trained", "validated", "deprecated", "failed"] = "unavailable"
    model: ModelInfo | None = None
    prediction: dict[str, Any] | None = None
    limitations: list[str]


class ScreeningProfileResponse(BaseModel):
    session_id: UUID
    mode: Literal["DEMO", "OBSERVATION_ONLY", "RESEARCH", "MODEL_INFERENCE", "UNAVAILABLE"]
    subject_id: str | None = None
    assessment_id: UUID | None = None
    trial_count: int = 0
    feature_schema_version: str = "1.0"
    available_modalities: list[str] = Field(default_factory=lambda: ["behavior"])
    missing_features: list[str] = Field(default_factory=list)
    domains: dict[str, dict[str, Any]]
    observations: list[str]
    data_quality: dict[str, Any]
    model: PredictionResponse
    limitations: list[str]


class DataQualityReport(BaseModel):
    status: Literal["ok", "warning", "invalid"]
    schema_version: str = "1.0"
    total_sessions: int
    total_trials: int
    valid_sessions: int
    invalid_sessions: int
    missing_feature_percentage: dict[str, float]
    gaze_availability: float
    speech_availability: float
    incomplete_trials: int
    duplicate_events: int
    outlier_counts: dict[str, int]
    missing_feature_rates: dict[str, float] = Field(default_factory=dict)
    invalid_feature_counts: dict[str, int] = Field(default_factory=dict)
    zero_trial_sessions: int = 0
    warnings: list[str] = Field(default_factory=list)
