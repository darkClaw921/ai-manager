"""Add qualification_script_id FK to faq_items/objection_scripts and score_config to qualification_scripts.

Revision ID: 0006
Revises: 0005
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. faq_items: add qualification_script_id FK
    op.add_column(
        "faq_items",
        sa.Column("qualification_script_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_faq_items_qualification_script_id",
        "faq_items",
        "qualification_scripts",
        ["qualification_script_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_faq_items_qualification_script_id",
        "faq_items",
        ["qualification_script_id"],
    )

    # 2. objection_scripts: add qualification_script_id FK
    op.add_column(
        "objection_scripts",
        sa.Column("qualification_script_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_objection_scripts_qualification_script_id",
        "objection_scripts",
        "qualification_scripts",
        ["qualification_script_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_objection_scripts_qualification_script_id",
        "objection_scripts",
        ["qualification_script_id"],
    )

    # 3. qualification_scripts: add score_config JSON column
    op.add_column(
        "qualification_scripts",
        sa.Column("score_config", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    # 3. Remove score_config
    op.drop_column("qualification_scripts", "score_config")

    # 2. Remove objection_scripts FK
    op.drop_index(
        "ix_objection_scripts_qualification_script_id",
        table_name="objection_scripts",
    )
    op.drop_constraint(
        "fk_objection_scripts_qualification_script_id",
        "objection_scripts",
        type_="foreignkey",
    )
    op.drop_column("objection_scripts", "qualification_script_id")

    # 1. Remove faq_items FK
    op.drop_index(
        "ix_faq_items_qualification_script_id",
        table_name="faq_items",
    )
    op.drop_constraint(
        "fk_faq_items_qualification_script_id",
        "faq_items",
        type_="foreignkey",
    )
    op.drop_column("faq_items", "qualification_script_id")
