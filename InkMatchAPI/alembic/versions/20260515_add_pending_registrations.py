"""add pending registrations

Revision ID: 20260515_add_pending_registrations
Revises: f6a7b8c9d0e1
Create Date: 2026-05-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '20260515_add_pending_registrations'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pending_registrations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=True),
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('profile_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('preferred_style_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('preferred_tag_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('preferences_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('master_profile_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('workplace_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('code', sa.String(length=16), nullable=True),
        sa.Column('code_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_pending_registrations_token', 'pending_registrations', ['token'], unique=True)
    op.create_index('ix_pending_registrations_email', 'pending_registrations', ['email'], unique=False)
    op.create_index('ix_pending_registrations_phone', 'pending_registrations', ['phone'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_pending_registrations_phone', table_name='pending_registrations')
    op.drop_index('ix_pending_registrations_email', table_name='pending_registrations')
    op.drop_index('ix_pending_registrations_token', table_name='pending_registrations')
    op.drop_table('pending_registrations')
