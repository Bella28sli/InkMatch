from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.enums import DocumentType, VerificationStatus


class MasterVerificationRequest(Base):
    __tablename__ = "master_verification_requests"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    master_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status"),
        nullable=False,
        server_default="draft",
    )
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_moderator_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class MasterVerificationPersonalData(Base):
    __tablename__ = "master_verification_personal_data"

    request_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("master_verification_requests.id"), primary_key=True
    )
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    second_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_name: Mapped[str] = mapped_column(String(64), nullable=False)
    patronymic: Mapped[str | None] = mapped_column(String(64), nullable=True)
    birth_date: Mapped[date] = mapped_column(nullable=False)
    citizenship: Mapped[str | None] = mapped_column(String(64), nullable=True)


class MasterVerificationDocument(Base):
    __tablename__ = "master_verification_documents"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    request_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("master_verification_requests.id"), nullable=False
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="verification_document_type"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issuer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issued_date: Mapped[date | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MasterVerificationDocumentFile(Base):
    __tablename__ = "master_verification_document_files"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("master_verification_documents.id"), nullable=False
    )
    file_url: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
