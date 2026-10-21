"""Research predictions (outputs of synthetic research models, kept apart from screening results).

Revision ID: 0004_research_predictions
Revises: 0003_screening_results
Create Date: 2026-10-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_research_predictions"
down_revision: Union[str, Sequence[str], None] = "0003_screening_results"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_predictions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("child_id", sa.Uuid(), sa.ForeignKey("child_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), sa.ForeignKey("assessment_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_id", sa.String(120), nullable=False),
        sa.Column("model_version", sa.String(40), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(80), nullable=False),
        sa.Column("feature_schema_version", sa.String(40), nullable=False),
        sa.Column("output_type", sa.String(40), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("assessment_id", "model_id", "model_version", name="uq_research_assessment_model"),
    )
    op.create_index("ix_research_predictions_child_id", "research_predictions", ["child_id"])
    op.create_index("ix_research_predictions_assessment_id", "research_predictions", ["assessment_id"])


def downgrade() -> None:
    op.drop_table("research_predictions")
