from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.enums import CollectionType, MediaType, OriginalAuthorType, SketchContentType, FileType


class Sketch(Base):
    __tablename__ = "sketches"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    author_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    content_type: Mapped[SketchContentType] = mapped_column(
        Enum(SketchContentType, name="sketch_content_type"), nullable=False
    )
    feed_visibility: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="public"
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    original_author_type: Mapped[OriginalAuthorType] = mapped_column(
        Enum(OriginalAuthorType, name="original_author_type"),
        nullable=False,
        server_default="unknown",
    )
    original_author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    original_author_user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    like_amount: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")


class SketchMedia(Base):
    __tablename__ = "sketch_media"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    sketch_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sketches.id", ondelete="CASCADE"), nullable=False
    )
    media_type: Mapped[MediaType] = mapped_column(
        Enum(MediaType, name="media_type"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    preview_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    phash: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SketchComment(Base):
    __tablename__ = "sketch_comments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    sketch_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sketches.id", ondelete="CASCADE"), nullable=False
    )
    author_user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    parent_comment_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sketch_comments.id", ondelete="CASCADE"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CommentAttachment(Base):
    __tablename__ = "comments_attachments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    comment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sketch_comments.id", ondelete="CASCADE"), nullable=False
    )
    file_url: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[FileType] = mapped_column(
        Enum(FileType, name="comment_file_type"), nullable=False
    )
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SketchStyle(Base):
    __tablename__ = "sketch_styles"

    sketch_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sketches.id", ondelete="CASCADE"), primary_key=True
    )
    style_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("styles.id"), primary_key=True
    )


class SketchTag(Base):
    __tablename__ = "sketch_tags"

    sketch_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sketches.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id"), primary_key=True
    )


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(64), nullable=False)


class Style(Base):
    __tablename__ = "styles"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    collection_type: Mapped[CollectionType] = mapped_column(
        Enum(CollectionType, name="collection_type"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CollectionItem(Base):
    __tablename__ = "collection_items"

    collection_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collections.id"), primary_key=True
    )
    sketch_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sketches.id", ondelete="CASCADE"), primary_key=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    work_duration_houres: Mapped[int | None] = mapped_column(Integer, nullable=True)
    work_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class SketchCommentLike(Base):
    __tablename__ = "sketch_comment_likes"

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    comment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sketch_comments.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SketchPin(Base):
    __tablename__ = "sketch_pins"

    sketch_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sketches.id", ondelete="CASCADE"), primary_key=True
    )
    pinned_comment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sketch_comments.id", ondelete="CASCADE"), nullable=False
    )
    pinned_by_user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    pinned_reason: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="inkmatch_review"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SketchLike(Base):
    __tablename__ = "sketch_likes"

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    sketch_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sketches.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FeedPreferredTag(Base):
    __tablename__ = "feed_preferred_tags"

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id"), primary_key=True
    )
    weight: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)


class FeedPreferredStyle(Base):
    __tablename__ = "feed_preferred_styles"

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    style_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("styles.id"), primary_key=True
    )
    weight: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
