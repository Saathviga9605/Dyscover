"""Persistent refresh tokens, token versioning, and Lexi conversations.

Revision ID: 0002_auth_tokens_lexi
Revises: 1c08bf9c22ca
Create Date: 2026-10-20

Also repairs databases that were created with ``create_all`` before the
baseline existed:
- adds legacy columns that the old startup hook used to patch in on SQLite;
- on PostgreSQL, recreates child-data foreign keys with ``ON DELETE CASCADE``.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_auth_tokens_lexi"
down_revision: Union[str, Sequence[str], None] = "1c08bf9c22ca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Columns the pre-migration startup hook added with ALTER TABLE on SQLite.
_LEGACY_COLUMNS: list[tuple[str, sa.Column]] = [
    ("speech_sessions", sa.Column("expected_text", sa.Text(), nullable=False, server_default="")),
    ("speech_sessions", sa.Column("features", sa.JSON())),
    ("speech_sessions", sa.Column("locale", sa.String(16), nullable=False, server_default="en-US")),
    ("assessment_sessions", sa.Column("created_at", sa.DateTime())),
    ("assessment_sessions", sa.Column("language", sa.String(16), nullable=False, server_default="en")),
    ("assessment_sessions", sa.Column("locale", sa.String(16), nullable=False, server_default="en-US")),
    ("assessment_sessions", sa.Column("content_version", sa.String(16), nullable=False, server_default="1.0")),
    ("gaze_samples", sa.Column("quality", sa.String(24), nullable=False, server_default="tracking")),
    ("gaze_samples", sa.Column("provider", sa.String(80))),
    ("gaze_samples", sa.Column("viewport_width", sa.Integer())),
    ("gaze_samples", sa.Column("viewport_height", sa.Integer())),
    ("game_sessions", sa.Column("language", sa.String(16), nullable=False, server_default="en")),
    ("game_sessions", sa.Column("content_version", sa.String(16), nullable=False, server_default="1.0")),
    ("trials", sa.Column("language", sa.String(16), nullable=False, server_default="en")),
    ("trials", sa.Column("content_version", sa.String(16), nullable=False, server_default="1.0")),
    ("interaction_events", sa.Column("language", sa.String(16), nullable=False, server_default="en")),
    ("practice_sessions", sa.Column("language", sa.String(16), nullable=False, server_default="en")),
    ("users", sa.Column("display_name", sa.String(120))),
    ("users", sa.Column("role", sa.String(32), nullable=False, server_default="parent")),
    ("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())),
    ("users", sa.Column("password_hash", sa.String(255))),
]

# (table, column, referenced table) for foreign keys that must cascade.
_CASCADE_FKS = [
    ("child_profiles", "owner_id", "users"),
    ("educator_learner_assignments", "educator_id", "users"),
    ("educator_learner_assignments", "child_id", "child_profiles"),
    ("assessment_sessions", "child_id", "child_profiles"),
    ("game_sessions", "assessment_session_id", "assessment_sessions"),
    ("trials", "game_session_id", "game_sessions"),
    ("interaction_events", "trial_id", "trials"),
    ("interaction_events", "session_id", "assessment_sessions"),
    ("gaze_samples", "trial_id", "trials"),
    ("fixations", "trial_id", "trials"),
    ("feature_vectors", "trial_id", "trials"),
    ("session_feature_vectors", "assessment_id", "assessment_sessions"),
    ("assessment_summaries", "assessment_id", "assessment_sessions"),
    ("speech_sessions", "assessment_id", "assessment_sessions"),
    ("speech_sessions", "trial_id", "trials"),
    ("practice_sessions", "child_id", "child_profiles"),
    ("practice_events", "practice_session_id", "practice_sessions"),
]


def _add_missing_legacy_columns(bind) -> None:
    inspector = sa.inspect(bind)
    for table, column in _LEGACY_COLUMNS:
        existing = {col["name"] for col in inspector.get_columns(table)}
        if column.name not in existing:
            op.add_column(table, column.copy())


def _cascade_postgres_foreign_keys(bind) -> None:
    inspector = sa.inspect(bind)
    for table, column, referred in _CASCADE_FKS:
        for fk in inspector.get_foreign_keys(table):
            if fk["constrained_columns"] == [column] and fk["referred_table"] == referred:
                if (fk.get("options") or {}).get("ondelete", "").upper() == "CASCADE":
                    continue
                op.drop_constraint(fk["name"], table, type_="foreignkey")
                op.create_foreign_key(fk["name"], table, referred, [column], ["id"], ondelete="CASCADE")


def upgrade() -> None:
    bind = op.get_bind()
    _add_missing_legacy_columns(bind)
    if bind.dialect.name == "postgresql":
        _cascade_postgres_foreign_keys(bind)

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime()),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(120)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_user_updated", "conversations", ["user_id", "updated_at"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("model", sa.String(80)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_conversation_created", "messages", ["conversation_id", "created_at"])


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("refresh_tokens")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("token_version")
