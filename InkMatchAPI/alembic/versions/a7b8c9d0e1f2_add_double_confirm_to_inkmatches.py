"""add double confirmation fields to inkmatches

Revision ID: a7b8c9d0e1f2
Revises: f1c2d3e4f5a6
Create Date: 2026-02-18 22:05:00
"""

from alembic import op
import sqlalchemy as sa


revision = 'a7b8c9d0e1f2'
down_revision = 'f1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('inkmatches', sa.Column('client_confirmed', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('inkmatches', sa.Column('master_confirmed', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('inkmatches', sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('inkmatches', 'confirmed_at')
    op.drop_column('inkmatches', 'master_confirmed')
    op.drop_column('inkmatches', 'client_confirmed')
