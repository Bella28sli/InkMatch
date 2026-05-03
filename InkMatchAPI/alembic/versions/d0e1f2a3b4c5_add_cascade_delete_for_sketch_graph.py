"""add cascade delete for sketch graph

Revision ID: d0e1f2a3b4c5
Revises: c4d5e6f7a8b9
Create Date: 2026-05-01 00:00:00
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = 'd0e1f2a3b4c5'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    fk_pairs = [
        ('collection_items', 'collection_items_sketch_id_fkey', 'sketch_id', 'sketches', 'id'),
        ('sketch_media', 'sketch_media_sketch_id_fkey', 'sketch_id', 'sketches', 'id'),
        ('sketch_comments', 'sketch_comments_sketch_id_fkey', 'sketch_id', 'sketches', 'id'),
        ('sketch_comments', 'sketch_comments_parent_comment_id_fkey', 'parent_comment_id', 'sketch_comments', 'id'),
        ('comments_attachments', 'comments_attachments_comment_id_fkey', 'comment_id', 'sketch_comments', 'id'),
        ('sketch_styles', 'sketch_styles_sketch_id_fkey', 'sketch_id', 'sketches', 'id'),
        ('sketch_tags', 'sketch_tags_sketch_id_fkey', 'sketch_id', 'sketches', 'id'),
        ('sketch_comment_likes', 'sketch_comment_likes_comment_id_fkey', 'comment_id', 'sketch_comments', 'id'),
        ('sketch_pins', 'sketch_pins_sketch_id_fkey', 'sketch_id', 'sketches', 'id'),
        ('sketch_pins', 'sketch_pins_pinned_comment_id_fkey', 'pinned_comment_id', 'sketch_comments', 'id'),
        ('inkmatch_requests', 'inkmatch_requests_sketch_id_fkey', 'sketch_id', 'sketches', 'id'),
        ('client_inkmatch_params', 'client_inkmatch_params_request_id_fkey', 'request_id', 'inkmatch_requests', 'id'),
        ('master_inkmatch_offer', 'master_inkmatch_offer_request_id_fkey', 'request_id', 'inkmatch_requests', 'id'),
        ('inkmatches', 'inkmatches_sketch_id_fkey', 'sketch_id', 'sketches', 'id'),
        ('inkmatches', 'inkmatches_client_request_id_fkey', 'client_request_id', 'inkmatch_requests', 'id'),
        ('inkmatches', 'inkmatches_master_request_id_fkey', 'master_request_id', 'inkmatch_requests', 'id'),
        ('inkmatch_reviews', 'inkmatch_reviews_inkmatch_id_fkey', 'inkmatch_id', 'inkmatches', 'id'),
    ]

    for table, constraint, column, ref_table, ref_column in fk_pairs:
        op.drop_constraint(constraint, table, type_='foreignkey')
        op.create_foreign_key(
            constraint,
            table,
            ref_table,
            [column],
            [ref_column],
            ondelete='CASCADE',
        )


def downgrade() -> None:
    fk_pairs = [
        ('collection_items', 'collection_items_sketch_id_fkey', 'sketch_id', 'sketches', 'id'),
        ('sketch_media', 'sketch_media_sketch_id_fkey', 'sketch_id', 'sketches', 'id'),
        ('sketch_comments', 'sketch_comments_sketch_id_fkey', 'sketch_id', 'sketches', 'id'),
        ('sketch_comments', 'sketch_comments_parent_comment_id_fkey', 'parent_comment_id', 'sketch_comments', 'id'),
        ('comments_attachments', 'comments_attachments_comment_id_fkey', 'comment_id', 'sketch_comments', 'id'),
        ('sketch_styles', 'sketch_styles_sketch_id_fkey', 'sketch_id', 'sketches', 'id'),
        ('sketch_tags', 'sketch_tags_sketch_id_fkey', 'sketch_id', 'sketches', 'id'),
        ('sketch_comment_likes', 'sketch_comment_likes_comment_id_fkey', 'comment_id', 'sketch_comments', 'id'),
        ('sketch_pins', 'sketch_pins_sketch_id_fkey', 'sketch_id', 'sketches', 'id'),
        ('sketch_pins', 'sketch_pins_pinned_comment_id_fkey', 'pinned_comment_id', 'sketch_comments', 'id'),
        ('inkmatch_requests', 'inkmatch_requests_sketch_id_fkey', 'sketch_id', 'sketches', 'id'),
        ('client_inkmatch_params', 'client_inkmatch_params_request_id_fkey', 'request_id', 'inkmatch_requests', 'id'),
        ('master_inkmatch_offer', 'master_inkmatch_offer_request_id_fkey', 'request_id', 'inkmatch_requests', 'id'),
        ('inkmatches', 'inkmatches_sketch_id_fkey', 'sketch_id', 'sketches', 'id'),
        ('inkmatches', 'inkmatches_client_request_id_fkey', 'client_request_id', 'inkmatch_requests', 'id'),
        ('inkmatches', 'inkmatches_master_request_id_fkey', 'master_request_id', 'inkmatch_requests', 'id'),
        ('inkmatch_reviews', 'inkmatch_reviews_inkmatch_id_fkey', 'inkmatch_id', 'inkmatches', 'id'),
    ]

    for table, constraint, column, ref_table, ref_column in fk_pairs:
        op.drop_constraint(constraint, table, type_='foreignkey')
        op.create_foreign_key(
            constraint,
            table,
            ref_table,
            [column],
            [ref_column],
        )
