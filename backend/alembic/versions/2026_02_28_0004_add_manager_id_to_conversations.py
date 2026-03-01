"""Add manager_id FK to conversations table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("manager_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_conversations_manager_id",
        "conversations",
        "admin_users",
        ["manager_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_conversations_manager_id",
        "conversations",
        type_="foreignkey",
    )
    op.drop_column("conversations", "manager_id")
