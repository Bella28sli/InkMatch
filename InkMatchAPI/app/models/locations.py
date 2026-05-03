from datetime import datetime
from uuid import uuid4

from sqlalchemy import Enum, String, DateTime, Numeric, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.enums import LocationPrecisionLevel, LocationProvider, WorkplaceDisplayMode


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    country: Mapped[str] = mapped_column(String(128), nullable=False)
    region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    locality: Mapped[str] = mapped_column(String(128), nullable=False)
    address_line: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entrance: Mapped[str | None] = mapped_column(String(32), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lat: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    lon: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    precision_level: Mapped[LocationPrecisionLevel] = mapped_column(
        Enum(LocationPrecisionLevel, name="location_precision_level"), nullable=False
    )
    provider: Mapped[LocationProvider | None] = mapped_column(
        Enum(LocationProvider, name="location_provider"), nullable=True
    )
    provider_place_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MetroStation(Base):
    __tablename__ = "metro_stations"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    city_location_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    line_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lat: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    lon: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False)


class MasterWorkplace(Base):
    __tablename__ = "master_workplaces"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    master_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    location_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False
    )
    is_home_studio: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    studio_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    public_display_mode: Mapped[WorkplaceDisplayMode] = mapped_column(
        Enum(WorkplaceDisplayMode, name="workplace_display_mode"),
        nullable=False,
        server_default="street",
    )
    public_metro_station_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("metro_stations.id"), nullable=True
    )
    public_text_override: Mapped[str | None] = mapped_column(String(255), nullable=True)
    show_on_map: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    public_lat: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    public_lon: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
