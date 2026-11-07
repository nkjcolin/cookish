"""Let recipes written in grams count against a kitchen kept in pieces.

Revision ID: 9b4e1c7d2a60
Revises: 6f2c8d471a90

The seed sets the value for the ingredients that need it on every deploy.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9b4e1c7d2a60"
down_revision: str | Sequence[str] | None = "6f2c8d471a90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ingredients", sa.Column("grams_per_piece", sa.Numeric(), nullable=True))


def downgrade() -> None:
    op.drop_column("ingredients", "grams_per_piece")
