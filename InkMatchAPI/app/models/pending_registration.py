from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class PendingRegistration(Base):
    __tablename__ = "pending_registrations"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    profile_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    preferred_style_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    preferred_tag_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    preferences_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    master_profile_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    workplace_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
