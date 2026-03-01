"""Change faq_items.keywords from text[] to JSONB to match model.

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Convert text[] column to jsonb, preserving data
    op.execute(
        """
        ALTER TABLE faq_items
        ALTER COLUMN keywords TYPE JSONB
        USING to_jsonb(keywords);
        """
    )


def downgrade() -> None:
    # Convert jsonb back to text[]
    op.execute(
        """
        ALTER TABLE faq_items
        ALTER COLUMN keywords TYPE TEXT[]
        USING ARRAY(SELECT jsonb_array_elements_text(keywords));
        """
    )
