"""add skipped to verification_status

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7
Create Date: 2026-05-01 00:00:00
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = 'c4d5e6f7a8b9'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    with op.get_context().autocommit_block():
        bind.exec_driver_sql(
            "ALTER TYPE verification_status ADD VALUE IF NOT EXISTS 'skipped'"
        )


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum value without recreating the type and
    # rewriting dependent columns, so keep this downgrade intentionally empty.
    pass
