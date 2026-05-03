from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.enums import InkmatchRequestStatus, InkmatchStatus, RequestCreatorRole, SearchMode, WorkplaceType, FileType


class InkmatchRequest(Base):
    __tablename__ = "inkmatch_requests"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    created_by_user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_by_role: Mapped[RequestCreatorRole] = mapped_column(
        Enum(RequestCreatorRole, name="request_creator_role"), nullable=False
    )
    sketch_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sketches.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[InkmatchRequestStatus] = mapped_column(
        Enum(InkmatchRequestStatus, name="inkmatch_request_status"),
        nullable=False,
        server_default="active",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ClientInkmatchParams(Base):
    __tablename__ = "client_inkmatch_params"

    request_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inkmatch_requests.id"), primary_key=True
    )
    size_sm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    search_mode: Mapped[SearchMode] = mapped_column(
        Enum(SearchMode, name="client_search_mode"), nullable=False
    )
    city_location_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True
    )
    region_location_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True
    )
    center_lat: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    center_lon: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    radius_meters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preferred_experience_years_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preferred_rating_min: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    preferred_workplace: Mapped[WorkplaceType | None] = mapped_column(
        Enum(WorkplaceType, name="preferred_workplace"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class MasterInkmatchOffer(Base):
    __tablename__ = "master_inkmatch_offer"

    request_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inkmatch_requests.id"), primary_key=True
    )
    offer_price: Mapped[int] = mapped_column(Integer, nullable=False)
    offer_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Inkmatch(Base):
    __tablename__ = "inkmatches"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    sketch_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sketches.id", ondelete="CASCADE"), nullable=False
    )
    client_request_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inkmatch_requests.id", ondelete="CASCADE"), nullable=False
    )
    master_request_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inkmatch_requests.id", ondelete="CASCADE"), nullable=False
    )
    chat_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chats.id"), nullable=True
    )
    client_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    master_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[InkmatchStatus] = mapped_column(
        Enum(InkmatchStatus, name="inkmatch_status"), nullable=False, server_default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class InkmatchReview(Base):
    __tablename__ = "inkmatch_reviews"
    __table_args__ = (UniqueConstraint("inkmatch_id", name="uq_inkmatch_review_inkmatch"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    inkmatch_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inkmatches.id", ondelete="CASCADE"), nullable=False
    )
    rating_overall: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rating_communication: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rating_cleanliness: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rating_quality: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rating_punctuality: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rating_price_fairness: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class InkmatchReviewAttachment(Base):
    __tablename__ = "inkmatch_review_attachments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    review_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inkmatch_reviews.id"), nullable=False
    )
    file_url: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[FileType] = mapped_column(
        Enum(FileType, name="inkmatch_review_file_type"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
