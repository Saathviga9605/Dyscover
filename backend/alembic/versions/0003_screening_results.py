"""Screening results (outputs of eligible production screening models).

Revision ID: 0003_screening_results
Revises: 0002_auth_tokens_lexi
Create Date: 2026-10-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_screening_results"
down_revision: Union[str, Sequence[str], None] = "0002_auth_tokens_lexi"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "screening_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("child_id", sa.Uuid(), sa.ForeignKey("child_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), sa.ForeignKey("assessment_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_id", sa.String(120), nullable=False),
        sa.Column("model_version", sa.String(40), nullable=False),
        sa.Column("feature_schema_version", sa.String(40), nullable=False),
        sa.Column("output_type", sa.String(40), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("assessment_id", "model_id", "model_version", name="uq_screening_assessment_model"),
    )
    op.create_index("ix_screening_results_child_id", "screening_results", ["child_id"])
    op.create_index("ix_screening_results_assessment_id", "screening_results", ["assessment_id"])


def downgrade() -> None:
    op.drop_table("screening_results")
