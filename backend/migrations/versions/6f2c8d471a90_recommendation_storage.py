"""Persist recommendation snapshots, ordered learning and confirmation replay.

Revision ID: 6f2c8d471a90
Revises: d0ae2870ce7e

Legacy rows deliberately retain NULL snapshots. Existing taste weights and all
inventory/history data are preserved; the adapter rejects unsupported legacy
workflow state rather than inventing historical responses.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "6f2c8d471a90"
down_revision: str | Sequence[str] | None = "d0ae2870ce7e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("recommendation_state", postgresql.JSONB(), nullable=True))
    op.add_column(
        "cook_records", sa.Column("selection_snapshot", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "cook_records", sa.Column("confirmation_snapshot", postgresql.JSONB(), nullable=True)
    )
    op.add_column("baskets", sa.Column("planning_snapshot", postgresql.JSONB(), nullable=True))
    op.create_table(
        "recommendation_learning",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("state", postgresql.JSONB(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name=op.f("fk_recommendation_learning_household_id_households"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_recommendation_learning_updated_by_users"),
        ),
        sa.PrimaryKeyConstraint("household_id", name=op.f("pk_recommendation_learning")),
    )
    op.create_table(
        "recommendation_confirmations",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.Column("response_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("stock_event_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "operation IN ('cook', 'shop')",
            name=op.f("ck_recommendation_confirmations_operation_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name=op.f("fk_recommendation_confirmations_household_id_households"),
        ),
        sa.ForeignKeyConstraint(
            ["stock_event_id"],
            ["stock_events.id"],
            name=op.f("fk_recommendation_confirmations_stock_event_id_stock_events"),
        ),
        sa.PrimaryKeyConstraint(
            "household_id", "idempotency_key", name=op.f("pk_recommendation_confirmations")
        ),
    )


def downgrade() -> None:
    op.drop_table("recommendation_confirmations")
    op.drop_table("recommendation_learning")
    op.drop_column("baskets", "planning_snapshot")
    op.drop_column("cook_records", "confirmation_snapshot")
    op.drop_column("cook_records", "selection_snapshot")
    op.drop_column("sessions", "recommendation_state")
