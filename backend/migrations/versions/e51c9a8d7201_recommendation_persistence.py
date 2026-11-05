"""Recommendation snapshots, ordered learning evidence and confirmation replay.

Revision ID: e51c9a8d7201
Revises: d0ae2870ce7e
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e51c9a8d7201"
down_revision = "d0ae2870ce7e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sessions", sa.Column("recommendation_state", postgresql.JSONB(), nullable=True))
    op.add_column("cook_records", sa.Column("selection_snapshot", postgresql.JSONB(), nullable=True))
    op.add_column("cook_records", sa.Column("confirmation_snapshot", postgresql.JSONB(), nullable=True))
    op.add_column("baskets", sa.Column("planning_snapshot", postgresql.JSONB(), nullable=True))
    op.create_table(
        "recommendation_learning",
        sa.Column("household_id", sa.Uuid(), sa.ForeignKey("households.id"), primary_key=True),
        sa.Column("state", postgresql.JSONB(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "recommendation_confirmations",
        sa.Column("household_id", sa.Uuid(), sa.ForeignKey("households.id"), primary_key=True),
        sa.Column("idempotency_key", sa.Uuid(), primary_key=True),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.Column("response_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("stock_event_id", sa.Uuid(), sa.ForeignKey("stock_events.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("operation IN ('cook', 'shop')", name=op.f("ck_recommendation_confirmations_operation_valid")),
    )


def downgrade():
    op.drop_table("recommendation_confirmations")
    op.drop_table("recommendation_learning")
    op.drop_column("baskets", "planning_snapshot")
    op.drop_column("cook_records", "confirmation_snapshot")
    op.drop_column("cook_records", "selection_snapshot")
    op.drop_column("sessions", "recommendation_state")
