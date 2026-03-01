"""Add qualification_script_id FK to channels table.

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column("qualification_script_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_channels_qualification_script_id",
        "channels",
        "qualification_scripts",
        ["qualification_script_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_channels_qualification_script_id",
        "channels",
        type_="foreignkey",
    )
    op.drop_column("channels", "qualification_script_id")
