from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum, Integer, Numeric, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.enums import SearchMode, WorkplaceType


class Profile(Base):
    __tablename__ = "profiles"

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    nickname: Mapped[str] = mapped_column(String(64), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    bio: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    nickname_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    home_location_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True
    )
    default_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default="RUB"
    )


class MasterProfile(Base):
    __tablename__ = "master_profiles"

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    verification_skipped: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    rating_avg: Mapped[float] = mapped_column(
        Numeric(3, 2), nullable=False, server_default="0"
    )
    completed_sessions_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

class InkmatchDefaults(Base):
    __tablename__ = "inkmatch_defaults"

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    experience_years_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_min: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    workplace: Mapped[WorkplaceType | None] = mapped_column(
        Enum(WorkplaceType, name="workplace_type"), nullable=True
    )
    search_mode: Mapped[SearchMode] = mapped_column(
        Enum(SearchMode, name="search_mode"),
        nullable=False,
        server_default="city",
    )
    city_location_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True
    )
    region_location_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True
    )
    radius_meters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    center_lat: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    center_lon: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    default_size_sm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_price_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_price_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )