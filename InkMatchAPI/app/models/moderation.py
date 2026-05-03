from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.enums import (
    AuditSource,
    AppealStatus,
    AppealTargetType,
    ComplaintStatus,
    ComplaintTargetType,
    FileType,
    ModerationActionType,
    ModerationQueueEntityType,
    ModerationQueueStatus,
)


class ModerationReason(Base):
    __tablename__ = "moderation_reasons"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    applies_to: Mapped[str] = mapped_column(String(64), nullable=False, server_default="general")
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="5")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class UserWarning(Base):
    __tablename__ = "user_warnings"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    issued_by_moderator_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    reason_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("moderation_reasons.id"), nullable=True
    )
    reason_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="active")
    related_restriction_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_restrictions.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ModerationQueueItem(Base):
    __tablename__ = "moderation_queue_items"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    entity_type: Mapped[ModerationQueueEntityType] = mapped_column(
        Enum(ModerationQueueEntityType, name="moderation_queue_entity_type"),
        nullable=False,
    )
    entity_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="3")
    status: Mapped[ModerationQueueStatus] = mapped_column(
        Enum(ModerationQueueStatus, name="moderation_queue_status"),
        nullable=False,
        server_default="open",
    )
    assigned_moderator_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    author_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    target_type: Mapped[ComplaintTargetType] = mapped_column(
        Enum(ComplaintTargetType, name="complaint_target_type"), nullable=False
    )
    target_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ComplaintStatus] = mapped_column(
        Enum(ComplaintStatus, name="complaint_status"),
        nullable=False,
        server_default="open",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Appeal(Base):
    __tablename__ = "appeals"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    appellant_user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    target_type: Mapped[AppealTargetType] = mapped_column(
        Enum(AppealTargetType, name="appeal_target_type"), nullable=False
    )
    target_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AppealStatus] = mapped_column(
        Enum(AppealStatus, name="appeal_status"),
        nullable=False,
        server_default="submitted",
    )
    reason_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    reviewed_by_moderator_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AppealAttachment(Base):
    __tablename__ = "appeal_attachments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    appeal_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("appeals.id"), nullable=False)
    file_url: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[FileType] = mapped_column(
        Enum(FileType, name="appeal_file_type"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ModerationAction(Base):
    __tablename__ = "moderation_actions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    moderator_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action_type: Mapped[ModerationActionType] = mapped_column(
        Enum(ModerationActionType, name="moderation_action_type"), nullable=False
    )
    target_type: Mapped[ComplaintTargetType] = mapped_column(
        Enum(ComplaintTargetType, name="moderation_target_type"), nullable=False
    )
    target_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    complaint_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("complaints.id"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    actor_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[AuditSource] = mapped_column(
        Enum(AuditSource, name="audit_source"), nullable=False
    )
    ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class AuditEventTarget(Base):
    __tablename__ = "audit_event_targets"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    audit_event_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_events.id"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
