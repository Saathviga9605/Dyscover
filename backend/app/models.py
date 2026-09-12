from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    children: Mapped[list["ChildProfile"]] = relationship(back_populates="owner")


class ChildProfile(Base):
    __tablename__ = "child_profiles"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    birth_year: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    owner: Mapped[User | None] = relationship(back_populates="children")
    assessments: Mapped[list["AssessmentSession"]] = relationship(back_populates="child")
    practice_sessions: Mapped[list["PracticeSession"]] = relationship(back_populates="child")


class AssessmentSession(Base):
    __tablename__ = "assessment_sessions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    child_id: Mapped[UUID] = mapped_column(ForeignKey("child_profiles.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="planned")
    version: Mapped[str] = mapped_column(String(32), default="stage-1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    child: Mapped[ChildProfile] = relationship(back_populates="assessments")
    games: Mapped[list["GameSession"]] = relationship(back_populates="assessment")


class GameSession(Base):
    __tablename__ = "game_sessions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    assessment_session_id: Mapped[UUID] = mapped_column(ForeignKey("assessment_sessions.id"), index=True)
    game_id: Mapped[str] = mapped_column(String(80), index=True)
    game_version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    score: Mapped[float | None] = mapped_column(Float)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    assessment: Mapped[AssessmentSession] = relationship(back_populates="games")
    trials: Mapped[list["Trial"]] = relationship(back_populates="game_session")


class Trial(Base):
    __tablename__ = "trials"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    game_session_id: Mapped[UUID] = mapped_column(ForeignKey("game_sessions.id"), index=True)
    trial_number: Mapped[int] = mapped_column(Integer)
    stimulus: Mapped[dict | list | str] = mapped_column(JSON)
    expected_response: Mapped[dict | list | str | None] = mapped_column(JSON)
    actual_response: Mapped[dict | list | str | None] = mapped_column(JSON)
    game_version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    domain: Mapped[str | None] = mapped_column(String(80))
    difficulty: Mapped[int] = mapped_column(Integer, default=1)
    score: Mapped[float] = mapped_column(Float, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    correctness: Mapped[bool | None] = mapped_column()
    reaction_time_ms: Mapped[int | None] = mapped_column(Integer)
    hesitation_time_ms: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    game_session: Mapped[GameSession] = relationship(back_populates="trials")
    events: Mapped[list["InteractionEvent"]] = relationship(back_populates="trial")


class InteractionEvent(Base):
    __tablename__ = "interaction_events"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    trial_id: Mapped[UUID] = mapped_column(ForeignKey("trials.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    session_id: Mapped[UUID | None] = mapped_column(ForeignKey("assessment_sessions.id"), index=True)
    game_id: Mapped[str | None] = mapped_column(String(80), index=True)
    performance_time: Mapped[float | None] = mapped_column(Float)
    sequence_number: Mapped[int | None] = mapped_column(Integer)
    schema_version: Mapped[str] = mapped_column(String(16), default="1.0")
    trial: Mapped[Trial] = relationship(back_populates="events")


class GazeSample(Base):
    __tablename__ = "gaze_samples"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    trial_id: Mapped[UUID] = mapped_column(ForeignKey("trials.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)


class Fixation(Base):
    __tablename__ = "fixations"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    trial_id: Mapped[UUID] = mapped_column(ForeignKey("trials.id"), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    duration_ms: Mapped[int] = mapped_column(Integer)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    target_type: Mapped[str | None] = mapped_column(String(40))
    target_id: Mapped[str | None] = mapped_column(String(120))


class FeatureVector(Base):
    __tablename__ = "feature_vectors"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    trial_id: Mapped[UUID] = mapped_column(ForeignKey("trials.id"), unique=True, index=True)
    features: Mapped[dict] = mapped_column(JSON, default=dict)


class SessionFeatureVector(Base):
    __tablename__ = "session_feature_vectors"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    assessment_id: Mapped[UUID] = mapped_column(ForeignKey("assessment_sessions.id"), unique=True, index=True)
    feature_schema_version: Mapped[str] = mapped_column(String(16), default="1.0")
    feature_extractor_version: Mapped[str] = mapped_column(String(16), default="1.0")
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    quality: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AssessmentSummary(Base):
    __tablename__ = "assessment_summaries"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    assessment_id: Mapped[UUID] = mapped_column(ForeignKey("assessment_sessions.id"), unique=True, index=True)
    schema_version: Mapped[str] = mapped_column(String(16), default="2.0")
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SpeechSession(Base):
    __tablename__ = "speech_sessions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    assessment_id: Mapped[UUID] = mapped_column(ForeignKey("assessment_sessions.id"), index=True)
    trial_id: Mapped[UUID | None] = mapped_column(ForeignKey("trials.id"), index=True)
    task_id: Mapped[str] = mapped_column(String(120))
    expected_text: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(16), default="en")
    audio_available: Mapped[bool] = mapped_column(default=False)
    provider: Mapped[str] = mapped_column(String(80), default="unconfigured")
    provider_version: Mapped[str] = mapped_column(String(40), default="unknown")
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


Index("ix_trials_game_number", Trial.game_session_id, Trial.trial_number, unique=True)


class PracticeSession(Base):
    """A remedial practice session — explicitly separate from assessment.

    Assessment sessions collect observations; practice sessions provide
    learning opportunities. ``mode`` is persisted as ``"practice"`` so that
    practice data can always be identified separately from assessment data.
    """

    __tablename__ = "practice_sessions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    child_id: Mapped[UUID] = mapped_column(ForeignKey("child_profiles.id"), index=True)
    mode: Mapped[str] = mapped_column(String(24), default="practice")
    activity_id: Mapped[str] = mapped_column(String(80), index=True)
    target_domain: Mapped[str] = mapped_column(String(80), index=True)
    difficulty: Mapped[int] = mapped_column(Integer, default=1)
    activity_version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    content_version: Mapped[str] = mapped_column(String(32), default="1.0")
    config_version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    status: Mapped[str] = mapped_column(String(24), default="planned", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    child: Mapped[ChildProfile] = relationship(back_populates="practice_sessions")
    events: Mapped[list["PracticeEvent"]] = relationship(back_populates="practice_session", cascade="all, delete-orphan")


class PracticeEvent(Base):
    """Structured practice telemetry mirroring the canonical event contract.

    Uses the same field vocabulary as assessment events (event_type,
    timestamp, sequence_number, payload, schema_version) while living in a
    separate, clearly marked ``practice`` collection so practice data can
    never be mistaken for assessment evidence.
    """

    __tablename__ = "practice_events"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    practice_session_id: Mapped[UUID] = mapped_column(ForeignKey("practice_sessions.id"), index=True)
    mode: Mapped[str] = mapped_column(String(24), default="practice")
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sequence_number: Mapped[int] = mapped_column(Integer, default=0)
    schema_version: Mapped[str] = mapped_column(String(16), default="2.0")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    practice_session: Mapped[PracticeSession] = relationship(back_populates="events")
