"""add warning history and reason scope

Revision ID: ab12cd34ef56
Revises: f6a7b8c9d0e1
Create Date: 2026-04-28 12:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'ab12cd34ef56'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'moderation_reasons',
        sa.Column('applies_to', sa.String(length=64), nullable=False, server_default='general'),
    )
    op.execute(
        """
        UPDATE moderation_reasons
        SET applies_to = CASE
          WHEN code LIKE 'complaint_%' OR code IN (
            'threats', 'self_harm', 'violence', 'illegal_services', 'scam',
            'impersonation', 'hate_speech', 'insult', 'spam', 'adult_content',
            'shocking', 'copyright_violation', 'privacy_violation', 'other'
          ) THEN 'complaint'
          WHEN code LIKE '%warning%' THEN 'warning'
          WHEN code LIKE '%restriction%' OR code LIKE '%block%' THEN 'restriction'
          ELSE 'moderation_reject'
        END
        """
    )

    op.create_table(
        'user_warnings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('issued_by_moderator_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reason_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reason_text', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('related_restriction_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['issued_by_moderator_id'], ['users.id']),
        sa.ForeignKeyConstraint(['reason_id'], ['moderation_reasons.id']),
        sa.ForeignKeyConstraint(['related_restriction_id'], ['user_restrictions.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_user_warnings_user_status', 'user_warnings', ['user_id', 'status'])


def downgrade() -> None:
    op.drop_index('ix_user_warnings_user_status', table_name='user_warnings')
    op.drop_table('user_warnings')
    op.drop_column('moderation_reasons', 'applies_to')
