"""add chat_id to inkmatches

Revision ID: f1c2d3e4f5a6
Revises: d9e7a1b2c3d4
Create Date: 2026-02-18 21:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = 'f1c2d3e4f5a6'
down_revision = 'd9e7a1b2c3d4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('inkmatches', sa.Column('chat_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_inkmatches_chat_id_chats',
        'inkmatches',
        'chats',
        ['chat_id'],
        ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_inkmatches_chat_id_chats', 'inkmatches', type_='foreignkey')
    op.drop_column('inkmatches', 'chat_id')
