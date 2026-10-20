"""Baseline schema (assessment, gaze, speech, practice, educator access).

Revision ID: 1c08bf9c22ca
Revises:
Create Date: 2026-10-20 11:35:20.974053

Historical note: databases created before this migration was made a real
baseline were built with ``Base.metadata.create_all`` and then stamped at this
revision, so this ``upgrade`` only ever runs against empty databases.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1c08bf9c22ca'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _fk(target: str) -> sa.ForeignKey:
    return sa.ForeignKey(target, ondelete="CASCADE")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), unique=True),
        sa.Column("display_name", sa.String(120)),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("password_hash", sa.String(255)),
    )
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "child_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), _fk("users.id")),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("birth_year", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_child_profiles_owner_id", "child_profiles", ["owner_id"])

    op.create_table(
        "educator_learner_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("educator_id", sa.Uuid(), _fk("users.id"), nullable=False),
        sa.Column("child_id", sa.Uuid(), _fk("child_profiles.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime()),
        sa.Column("revocation_reason", sa.String(200)),
    )
    op.create_index("ix_educator_learner_assignments_educator_id", "educator_learner_assignments", ["educator_id"])
    op.create_index("ix_educator_learner_assignments_child_id", "educator_learner_assignments", ["child_id"])
    op.create_index("ix_educator_learner_assignments_status", "educator_learner_assignments", ["status"])
    op.create_index("ix_educator_learner_status", "educator_learner_assignments", ["educator_id", "child_id", "status"], unique=True)

    op.create_table(
        "assessment_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("child_id", sa.Uuid(), _fk("child_profiles.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("locale", sa.String(16), nullable=False),
        sa.Column("content_version", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
    )
    op.create_index("ix_assessment_sessions_child_id", "assessment_sessions", ["child_id"])

    op.create_table(
        "game_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("assessment_session_id", sa.Uuid(), _fk("assessment_sessions.id"), nullable=False),
        sa.Column("game_id", sa.String(80), nullable=False),
        sa.Column("game_version", sa.String(32), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("content_version", sa.String(16), nullable=False),
        sa.Column("score", sa.Float()),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
    )
    op.create_index("ix_game_sessions_assessment_session_id", "game_sessions", ["assessment_session_id"])
    op.create_index("ix_game_sessions_game_id", "game_sessions", ["game_id"])

    op.create_table(
        "trials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("game_session_id", sa.Uuid(), _fk("game_sessions.id"), nullable=False),
        sa.Column("trial_number", sa.Integer(), nullable=False),
        sa.Column("stimulus", sa.JSON(), nullable=False),
        sa.Column("expected_response", sa.JSON()),
        sa.Column("actual_response", sa.JSON()),
        sa.Column("game_version", sa.String(32), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("content_version", sa.String(16), nullable=False),
        sa.Column("domain", sa.String(80)),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("correctness", sa.Boolean()),
        sa.Column("reaction_time_ms", sa.Integer()),
        sa.Column("hesitation_time_ms", sa.Integer()),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
    )
    op.create_index("ix_trials_game_session_id", "trials", ["game_session_id"])
    op.create_index("ix_trials_game_number", "trials", ["game_session_id", "trial_number"], unique=True)

    op.create_table(
        "interaction_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("trial_id", sa.Uuid(), _fk("trials.id"), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("session_id", sa.Uuid(), _fk("assessment_sessions.id")),
        sa.Column("game_id", sa.String(80)),
        sa.Column("performance_time", sa.Float()),
        sa.Column("sequence_number", sa.Integer()),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
    )
    op.create_index("ix_interaction_events_trial_id", "interaction_events", ["trial_id"])
    op.create_index("ix_interaction_events_event_type", "interaction_events", ["event_type"])
    op.create_index("ix_interaction_events_session_id", "interaction_events", ["session_id"])
    op.create_index("ix_interaction_events_game_id", "interaction_events", ["game_id"])

    op.create_table(
        "gaze_samples",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("trial_id", sa.Uuid(), _fk("trials.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("quality", sa.String(24), nullable=False),
        sa.Column("provider", sa.String(80)),
        sa.Column("viewport_width", sa.Integer()),
        sa.Column("viewport_height", sa.Integer()),
    )
    op.create_index("ix_gaze_samples_trial_id", "gaze_samples", ["trial_id"])

    op.create_table(
        "fixations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("trial_id", sa.Uuid(), _fk("trials.id"), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("target_type", sa.String(40)),
        sa.Column("target_id", sa.String(120)),
    )
    op.create_index("ix_fixations_trial_id", "fixations", ["trial_id"])

    op.create_table(
        "feature_vectors",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("trial_id", sa.Uuid(), _fk("trials.id"), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
    )
    op.create_index("ix_feature_vectors_trial_id", "feature_vectors", ["trial_id"], unique=True)

    op.create_table(
        "session_feature_vectors",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("assessment_id", sa.Uuid(), _fk("assessment_sessions.id"), nullable=False),
        sa.Column("feature_schema_version", sa.String(16), nullable=False),
        sa.Column("feature_extractor_version", sa.String(16), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("quality", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_session_feature_vectors_assessment_id", "session_feature_vectors", ["assessment_id"], unique=True)

    op.create_table(
        "assessment_summaries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("assessment_id", sa.Uuid(), _fk("assessment_sessions.id"), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_assessment_summaries_assessment_id", "assessment_summaries", ["assessment_id"], unique=True)

    op.create_table(
        "speech_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("assessment_id", sa.Uuid(), _fk("assessment_sessions.id"), nullable=False),
        sa.Column("trial_id", sa.Uuid(), _fk("trials.id")),
        sa.Column("task_id", sa.String(120), nullable=False),
        sa.Column("expected_text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("locale", sa.String(16), nullable=False),
        sa.Column("audio_available", sa.Boolean(), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("provider_version", sa.String(40), nullable=False),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("features", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_speech_sessions_assessment_id", "speech_sessions", ["assessment_id"])
    op.create_index("ix_speech_sessions_trial_id", "speech_sessions", ["trial_id"])

    op.create_table(
        "practice_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("child_id", sa.Uuid(), _fk("child_profiles.id"), nullable=False),
        sa.Column("mode", sa.String(24), nullable=False),
        sa.Column("activity_id", sa.String(80), nullable=False),
        sa.Column("target_domain", sa.String(80), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("activity_version", sa.String(32), nullable=False),
        sa.Column("content_version", sa.String(32), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("config_version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_index("ix_practice_sessions_child_id", "practice_sessions", ["child_id"])
    op.create_index("ix_practice_sessions_activity_id", "practice_sessions", ["activity_id"])
    op.create_index("ix_practice_sessions_target_domain", "practice_sessions", ["target_domain"])
    op.create_index("ix_practice_sessions_status", "practice_sessions", ["status"])

    op.create_table(
        "practice_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("practice_session_id", sa.Uuid(), _fk("practice_sessions.id"), nullable=False),
        sa.Column("mode", sa.String(24), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_practice_events_practice_session_id", "practice_events", ["practice_session_id"])
    op.create_index("ix_practice_events_event_type", "practice_events", ["event_type"])


def downgrade() -> None:
    for table in (
        "practice_events",
        "practice_sessions",
        "speech_sessions",
        "assessment_summaries",
        "session_feature_vectors",
        "feature_vectors",
        "fixations",
        "gaze_samples",
        "interaction_events",
        "trials",
        "game_sessions",
        "assessment_sessions",
        "educator_learner_assignments",
        "child_profiles",
        "users",
    ):
        op.drop_table(table)
