"""add comment/review complaint targets

Revision ID: b1c2d3e4f5a7
Revises: a7b8c9d0e1f2
Create Date: 2026-02-18 22:10:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = 'b1c2d3e4f5a7'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE complaint_target_type ADD VALUE IF NOT EXISTS 'comment'")
    op.execute("ALTER TYPE complaint_target_type ADD VALUE IF NOT EXISTS 'review'")
    op.execute("ALTER TYPE moderation_target_type ADD VALUE IF NOT EXISTS 'comment'")
    op.execute("ALTER TYPE moderation_target_type ADD VALUE IF NOT EXISTS 'review'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values safely in-place.
    pass
