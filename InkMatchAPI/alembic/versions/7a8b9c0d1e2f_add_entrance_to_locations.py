"""add entrance to locations

Revision ID: 7a8b9c0d1e2f
Revises: d0e1f2a3b4c5
Create Date: 2026-05-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '7a8b9c0d1e2f'
down_revision = 'd0e1f2a3b4c5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column['name'] for column in inspector.get_columns('locations')}
    if 'entrance' not in columns:
        op.add_column('locations', sa.Column('entrance', sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column('locations', 'entrance')
