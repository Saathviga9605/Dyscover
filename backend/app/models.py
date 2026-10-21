"""SQLAlchemy models.

Conventions:
- Timestamps are stored as naive UTC ``DateTime`` values (see ``app.core.time.utcnow``).
- Rows that belong to a child (assessments, practice, speech, gaze...) are reachable
  from ``ChildProfile`` and are removed with it. Foreign keys declare
  ``ON DELETE CASCADE`` so PostgreSQL enforces the same policy the ORM applies;
  account deletion additionally deletes in dependency order (``app.privacy.service``)
  so SQLite databases created before the cascade declarations behave identically.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(32), default="parent", index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Incremented on password change / "log out everywhere"; access tokens carry it
    # so previously issued tokens stop validating immediately.
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    children: Mapped[list["ChildProfile"]] = relationship(back_populates="owner")
    educator_assignments: Mapped[list["EducatorLearnerAssignment"]] = relationship(back_populates="educator")


class RefreshToken(Base):
    """Server-side record of an issued refresh token.

    Only a SHA-256 digest of the token is stored. Tokens rotate on every refresh;
    presenting an already-rotated token revokes the whole family (reuse detection).
    """

    __tablename__ = "refresh_tokens"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    family_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)


class ChildProfile(Base):
    __tablename__ = "child_profiles"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    # Nullable only for legacy rows created before authentication existed; every
    # API creation path sets an owner, and ownerless rows are inaccessible.
    owner_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    birth_year: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    owner: Mapped[User | None] = relationship(back_populates="children")
    assessments: Mapped[list["AssessmentSession"]] = relationship(back_populates="child", cascade="all, delete-orphan", passive_deletes=True)
    practice_sessions: Mapped[list["PracticeSession"]] = relationship(back_populates="child", cascade="all, delete-orphan", passive_deletes=True)
    educator_assignments: Mapped[list["EducatorLearnerAssignment"]] = relationship(back_populates="child", cascade="all, delete-orphan", passive_deletes=True)


class EducatorLearnerAssignment(Base):
    __tablename__ = "educator_learner_assignments"
    __table_args__ = (
        Index("ix_educator_learner_status", "educator_id", "child_id", "status", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    educator_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    child_id: Mapped[UUID] = mapped_column(ForeignKey("child_profiles.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    revocation_reason: Mapped[str | None] = mapped_column(String(200))
    educator: Mapped[User] = relationship(back_populates="educator_assignments")
    child: Mapped[ChildProfile] = relationship(back_populates="educator_assignments")


class AssessmentSession(Base):
    __tablename__ = "assessment_sessions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    child_id: Mapped[UUID] = mapped_column(ForeignKey("child_profiles.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="planned")
    version: Mapped[str] = mapped_column(String(32), default="stage-1")
    language: Mapped[str] = mapped_column(String(16), default="en")
    locale: Mapped[str] = mapped_column(String(16), default="en-US")
    content_version: Mapped[str] = mapped_column(String(16), default="1.0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    child: Mapped[ChildProfile] = relationship(back_populates="assessments")
    games: Mapped[list["GameSession"]] = relationship(back_populates="assessment", cascade="all, delete-orphan", passive_deletes=True)


class GameSession(Base):
    __tablename__ = "game_sessions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    assessment_session_id: Mapped[UUID] = mapped_column(ForeignKey("assessment_sessions.id", ondelete="CASCADE"), index=True)
    game_id: Mapped[str] = mapped_column(String(80), index=True)
    game_version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    language: Mapped[str] = mapped_column(String(16), default="en")
    content_version: Mapped[str] = mapped_column(String(16), default="1.0")
    score: Mapped[float | None] = mapped_column(Float)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    assessment: Mapped[AssessmentSession] = relationship(back_populates="games")
    trials: Mapped[list["Trial"]] = relationship(back_populates="game_session", cascade="all, delete-orphan", passive_deletes=True)


class Trial(Base):
    __tablename__ = "trials"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    game_session_id: Mapped[UUID] = mapped_column(ForeignKey("game_sessions.id", ondelete="CASCADE"), index=True)
    trial_number: Mapped[int] = mapped_column(Integer)
    stimulus: Mapped[dict | list | str] = mapped_column(JSON)
    expected_response: Mapped[dict | list | str | None] = mapped_column(JSON)
    actual_response: Mapped[dict | list | str | None] = mapped_column(JSON)
    game_version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    language: Mapped[str] = mapped_column(String(16), default="en")
    content_version: Mapped[str] = mapped_column(String(16), default="1.0")
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
    events: Mapped[list["InteractionEvent"]] = relationship(back_populates="trial", cascade="all, delete-orphan", passive_deletes=True)


class InteractionEvent(Base):
    __tablename__ = "interaction_events"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    trial_id: Mapped[UUID] = mapped_column(ForeignKey("trials.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    session_id: Mapped[UUID | None] = mapped_column(ForeignKey("assessment_sessions.id", ondelete="CASCADE"), index=True)
    game_id: Mapped[str | None] = mapped_column(String(80), index=True)
    performance_time: Mapped[float | None] = mapped_column(Float)
    sequence_number: Mapped[int | None] = mapped_column(Integer)
    schema_version: Mapped[str] = mapped_column(String(16), default="1.0")
    language: Mapped[str] = mapped_column(String(16), default="en")
    trial: Mapped[Trial] = relationship(back_populates="events")


class GazeSample(Base):
    __tablename__ = "gaze_samples"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    trial_id: Mapped[UUID] = mapped_column(ForeignKey("trials.id", ondelete="CASCADE"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    quality: Mapped[str] = mapped_column(String(24), default="tracking")
    provider: Mapped[str | None] = mapped_column(String(80))
    viewport_width: Mapped[int | None] = mapped_column(Integer)
    viewport_height: Mapped[int | None] = mapped_column(Integer)


class Fixation(Base):
    __tablename__ = "fixations"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    trial_id: Mapped[UUID] = mapped_column(ForeignKey("trials.id", ondelete="CASCADE"), index=True)
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
    trial_id: Mapped[UUID] = mapped_column(ForeignKey("trials.id", ondelete="CASCADE"), unique=True, index=True)
    features: Mapped[dict] = mapped_column(JSON, default=dict)


class SessionFeatureVector(Base):
    __tablename__ = "session_feature_vectors"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    assessment_id: Mapped[UUID] = mapped_column(ForeignKey("assessment_sessions.id", ondelete="CASCADE"), unique=True, index=True)
    feature_schema_version: Mapped[str] = mapped_column(String(16), default="1.0")
    feature_extractor_version: Mapped[str] = mapped_column(String(16), default="1.0")
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    quality: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AssessmentSummary(Base):
    __tablename__ = "assessment_summaries"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    assessment_id: Mapped[UUID] = mapped_column(ForeignKey("assessment_sessions.id", ondelete="CASCADE"), unique=True, index=True)
    schema_version: Mapped[str] = mapped_column(String(16), default="2.0")
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SpeechSession(Base):
    __tablename__ = "speech_sessions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    assessment_id: Mapped[UUID] = mapped_column(ForeignKey("assessment_sessions.id", ondelete="CASCADE"), index=True)
    trial_id: Mapped[UUID | None] = mapped_column(ForeignKey("trials.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[str] = mapped_column(String(120))
    expected_text: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(16), default="en")
    locale: Mapped[str] = mapped_column(String(16), default="en-US")
    audio_available: Mapped[bool] = mapped_column(default=False)
    provider: Mapped[str] = mapped_column(String(80), default="unconfigured")
    provider_version: Mapped[str] = mapped_column(String(40), default="unknown")
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    features_json: Mapped[dict | None] = mapped_column("features", JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


Index("ix_trials_game_number", Trial.game_session_id, Trial.trial_number, unique=True)


class PracticeSession(Base):
    """A remedial practice session — explicitly separate from assessment.

    Assessment sessions collect observations; practice sessions provide
    learning opportunities. ``mode`` is persisted as ``"practice"`` so that
    practice data can always be identified separately from assessment data.
    """

    __tablename__ = "practice_sessions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    child_id: Mapped[UUID] = mapped_column(ForeignKey("child_profiles.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(24), default="practice")
    activity_id: Mapped[str] = mapped_column(String(80), index=True)
    target_domain: Mapped[str] = mapped_column(String(80), index=True)
    difficulty: Mapped[int] = mapped_column(Integer, default=1)
    activity_version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    content_version: Mapped[str] = mapped_column(String(32), default="1.0")
    language: Mapped[str] = mapped_column(String(16), default="en")
    config_version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    status: Mapped[str] = mapped_column(String(24), default="planned", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    child: Mapped[ChildProfile] = relationship(back_populates="practice_sessions")
    events: Mapped[list["PracticeEvent"]] = relationship(back_populates="practice_session", cascade="all, delete-orphan", passive_deletes=True)


class PracticeEvent(Base):
    """Structured practice telemetry mirroring the canonical event contract.

    Uses the same field vocabulary as assessment events (event_type,
    timestamp, sequence_number, payload, schema_version) while living in a
    separate, clearly marked ``practice`` collection so practice data can
    never be mistaken for assessment evidence.
    """

    __tablename__ = "practice_events"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    practice_session_id: Mapped[UUID] = mapped_column(ForeignKey("practice_sessions.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(24), default="practice")
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    sequence_number: Mapped[int] = mapped_column(Integer, default=0)
    schema_version: Mapped[str] = mapped_column(String(16), default="2.0")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    practice_session: Mapped[PracticeSession] = relationship(back_populates="events")


class Conversation(Base):
    """A Lexi chat conversation owned by one user account."""

    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_user_updated", "user_id", "updated_at"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.created_at",
    )


class Message(Base):
    """A single Lexi chat message. ``role`` is ``user`` or ``assistant`` only;
    the system prompt is never persisted."""

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    # Provider model identifier for assistant messages (audit of what generated it).
    model: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class ScreeningResult(Base):
    """A stored screening output from an *eligible* production model.

    Only real model outputs are stored; "no model"/"insufficient evidence" states are
    computed on request. One row per (assessment, model, version): a new model
    version produces a new row instead of silently overwriting history.
    """

    __tablename__ = "screening_results"
    __table_args__ = (UniqueConstraint("assessment_id", "model_id", "model_version", name="uq_screening_assessment_model"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    child_id: Mapped[UUID] = mapped_column(ForeignKey("child_profiles.id", ondelete="CASCADE"), index=True)
    assessment_id: Mapped[UUID] = mapped_column(ForeignKey("assessment_sessions.id", ondelete="CASCADE"), index=True)
    model_id: Mapped[str] = mapped_column(String(120))
    model_version: Mapped[str] = mapped_column(String(40))
    feature_schema_version: Mapped[str] = mapped_column(String(40))
    output_type: Mapped[str] = mapped_column(String(40))
    score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ResearchPrediction(Base):
    """Output of a *synthetic research* model for one assessment.

    Deliberately a separate table from ``ScreeningResult``: research outputs are
    never clinical-risk records and are never read by the parent screening card.
    The artifact checksum pins the exact model that produced the score.
    """

    __tablename__ = "research_predictions"
    __table_args__ = (UniqueConstraint("assessment_id", "model_id", "model_version", name="uq_research_assessment_model"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    child_id: Mapped[UUID] = mapped_column(ForeignKey("child_profiles.id", ondelete="CASCADE"), index=True)
    assessment_id: Mapped[UUID] = mapped_column(ForeignKey("assessment_sessions.id", ondelete="CASCADE"), index=True)
    model_id: Mapped[str] = mapped_column(String(120))
    model_version: Mapped[str] = mapped_column(String(40))
    artifact_sha256: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(80))
    feature_schema_version: Mapped[str] = mapped_column(String(40))
    output_type: Mapped[str] = mapped_column(String(40))
    score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
