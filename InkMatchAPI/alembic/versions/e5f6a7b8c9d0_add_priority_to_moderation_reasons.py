"""add priority to moderation reasons

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-19 15:35:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'moderation_reasons',
        sa.Column('priority', sa.SmallInteger(), nullable=False, server_default='5'),
    )

    op.execute(
        """
        WITH reason_data(code, title, description, priority) AS (
          VALUES
            ('threats', 'Threats', 'Direct threats and intimidation', 1),
            ('self_harm', 'Self-harm', 'Self-harm promotion or encouragement', 1),
            ('violence', 'Violence', 'Graphic violence and cruelty', 1),
            ('illegal_services', 'Illegal services', 'Promotion of illegal services', 1),
            ('scam', 'Scam', 'Fraud, scam and payment abuse', 2),
            ('impersonation', 'Impersonation', 'Pretending to be another person or brand', 2),
            ('hate_speech', 'Hate speech', 'Content targeting protected groups', 2),
            ('insult', 'Insult and harassment', 'Abusive or insulting behavior', 3),
            ('spam', 'Spam', 'Repeated unsolicited content', 3),
            ('adult_content', 'Adult content', 'Sexual content and explicit imagery', 3),
            ('shocking', 'Shocking content', 'Disturbing or shocking content', 3),
            ('copyright_violation', 'Copyright violation', 'Unauthorized use of copyrighted content', 4),
            ('privacy_violation', 'Privacy violation', 'Leaking private or personal data', 4),
            ('other', 'Other', 'Other complaint reason', 5)
        )
        INSERT INTO moderation_reasons (id, code, title, description, priority, is_active)
        SELECT
          md5(random()::text || clock_timestamp()::text || code)::uuid,
          code,
          title,
          description,
          priority,
          true
        FROM reason_data rd
        WHERE NOT EXISTS (
          SELECT 1
          FROM moderation_reasons mr
          WHERE mr.code = rd.code
        );

        WITH reason_data(code, priority) AS (
          VALUES
            ('threats', 1),
            ('self_harm', 1),
            ('violence', 1),
            ('illegal_services', 1),
            ('scam', 2),
            ('impersonation', 2),
            ('hate_speech', 2),
            ('insult', 3),
            ('spam', 3),
            ('adult_content', 3),
            ('shocking', 3),
            ('copyright_violation', 4),
            ('privacy_violation', 4),
            ('other', 5)
        )
        UPDATE moderation_reasons mr
        SET priority = rd.priority
        FROM reason_data rd
        WHERE mr.code = rd.code;
        """
    )


def downgrade() -> None:
    op.drop_column('moderation_reasons', 'priority')
