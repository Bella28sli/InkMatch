"""add sketch likes table

Revision ID: d9e7a1b2c3d4
Revises: c1a2b3d4e5f6
Create Date: 2026-02-18 19:05:00
"""

from alembic import op
import sqlalchemy as sa


revision = 'd9e7a1b2c3d4'
down_revision = 'c1a2b3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'sketch_likes',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('sketch_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['sketch_id'], ['sketches.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('user_id', 'sketch_id'),
    )


def downgrade() -> None:
    op.drop_table('sketch_likes')
