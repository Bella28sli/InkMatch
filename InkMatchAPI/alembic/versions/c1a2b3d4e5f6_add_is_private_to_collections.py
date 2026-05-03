"""add_is_private_to_collections

Revision ID: c1a2b3d4e5f6
Revises: 10410f977d30
Create Date: 2026-02-13 11:50:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1a2b3d4e5f6'
down_revision = '10410f977d30'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'collections',
        sa.Column('is_private', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    op.drop_column('collections', 'is_private')
