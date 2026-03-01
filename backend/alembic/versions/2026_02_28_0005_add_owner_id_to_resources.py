"""Add owner_id to channels, scripts, and system_settings.

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

TABLES = ["channels", "qualification_scripts", "faq_items", "objection_scripts", "system_settings"]


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column("owner_id", sa.Uuid(), nullable=True),
        )
        op.create_foreign_key(
            f"fk_{table}_owner_id",
            table,
            "admin_users",
            ["owner_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(f"ix_{table}_owner_id", table, ["owner_id"])

    # system_settings: replace UNIQUE(key) with UNIQUE(key, owner_id)
    op.drop_constraint("system_settings_key_key", "system_settings", type_="unique")
    op.create_unique_constraint("uq_settings_key_owner", "system_settings", ["key", "owner_id"])


def downgrade() -> None:
    # system_settings: restore UNIQUE(key)
    op.drop_constraint("uq_settings_key_owner", "system_settings", type_="unique")
    op.create_unique_constraint("system_settings_key_key", "system_settings", ["key"])

    for table in reversed(TABLES):
        op.drop_index(f"ix_{table}_owner_id", table_name=table)
        op.drop_constraint(f"fk_{table}_owner_id", table, type_="foreignkey")
        op.drop_column(table, "owner_id")
