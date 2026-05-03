from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.enums import LocationPrecisionLevel, LocationProvider, UserRole, WorkplaceDisplayMode
from app.models.locations import Location, MasterWorkplace, MetroStation
from app.schemas.location import (
    GeocodeCandidateOut,
    LocationEnsureIn,
    LocationIn,
    LocationOut,
    MasterWorkplaceIn,
    MasterWorkplaceOut,
    MetroStationIn,
    NearbyMetroStationOut,
    MetroStationOut,
)
from app.services.yandex_geocoder_service import YandexGeocoderError, geocode

router = APIRouter()


def _location_out(row: Location):
    address_parts = [row.address_line, row.locality, row.region, row.country]
    short_parts = [row.locality, row.region]
    return {
        'id': str(row.id),
        'country': row.country,
        'region': row.region,
        'locality': row.locality,
        'address_line': row.address_line,
        'entrance': row.entrance,
        'postal_code': row.postal_code,
        'lat': float(row.lat),
        'lon': float(row.lon),
        'precision_level': row.precision_level.value,
        'provider': row.provider.value if row.provider else None,
        'provider_place_id': row.provider_place_id,
        'display_label': ', '.join([p for p in address_parts if p]),
        'short_label': ', '.join([p for p in short_parts if p]),
    }


def _metro_out(row: MetroStation):
    return {
        'id': str(row.id),
        'city_location_id': str(row.city_location_id),
        'name': row.name,
        'line_name': row.line_name,
        'lat': float(row.lat),
        'lon': float(row.lon),
        'color_hex': row.color_hex,
    }


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    earth_radius_m = 6371000.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return int(round(earth_radius_m * c))


def _public_workplace_address(
    row: MasterWorkplace,
    location: Location | None = None,
    metro_station: MetroStation | None = None,
):
    if row.public_text_override:
        return row.public_text_override
    if row.public_display_mode == WorkplaceDisplayMode.metro:
        if metro_station:
            return ', '.join([p for p in [f'м. {metro_station.name}', metro_station.line_name] if p])
        return row.public_text_override
    if location:
        if row.public_display_mode == WorkplaceDisplayMode.city_only:
            return ', '.join([p for p in [location.locality, location.region] if p])
        if row.public_display_mode == WorkplaceDisplayMode.street:
            return ', '.join([p for p in [location.address_line, location.locality] if p])
        if row.public_display_mode == WorkplaceDisplayMode.full_address:
            return ', '.join([p for p in [location.address_line, location.locality, location.region] if p])
    return None


def _workplace_out(
    row: MasterWorkplace,
    location: Location | None = None,
    metro_station: MetroStation | None = None,
):
    public_address = _public_workplace_address(row, location, metro_station)
    if row.studio_name and public_address:
        public_address = f'{row.studio_name}, {public_address}'
    elif row.studio_name:
        public_address = row.studio_name
    return {
        'id': str(row.id),
        'master_id': str(row.master_id),
        'location_id': str(row.location_id),
        'is_home_studio': bool(row.is_home_studio),
        'studio_name': row.studio_name,
        'public_display_mode': row.public_display_mode.value,
        'public_metro_station_id': str(row.public_metro_station_id) if row.public_metro_station_id else None,
        'public_text_override': row.public_text_override,
        'show_on_map': bool(row.show_on_map),
        'public_lat': float(row.public_lat) if row.public_lat is not None else None,
        'public_lon': float(row.public_lon) if row.public_lon is not None else None,
        'is_primary': bool(row.is_primary),
        'location': _location_out(location) if location else None,
        'public_metro_station': _metro_out(metro_station) if metro_station else None,
        'public_address': public_address,
    }


@router.get('/geocode', response_model=list[GeocodeCandidateOut])
def geocode_location(
    q: str = Query(min_length=1, max_length=255),
    limit: int = Query(default=5, ge=1, le=10),
):
    try:
        return geocode(q, limit=limit)
    except YandexGeocoderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get('/locations', response_model=list[LocationOut])
def list_locations(
    locality: str | None = Query(default=None),
    q: str | None = Query(default=None),
    precision_level: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(Location)
    if locality:
        stmt = stmt.where(Location.locality.ilike(f'%{locality}%'))
    if q:
        pattern = f'%{q.strip()}%'
        stmt = stmt.where(
            Location.country.ilike(pattern)
            | Location.region.ilike(pattern)
            | Location.locality.ilike(pattern)
            | Location.address_line.ilike(pattern)
        )
    if precision_level:
        try:
            precision = LocationPrecisionLevel(precision_level)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid precision_level') from exc
        stmt = stmt.where(Location.precision_level == precision)
    rows = db.execute(
        stmt.order_by(Location.country.asc(), Location.locality.asc(), Location.address_line.asc()).limit(limit)
    ).scalars().all()
    return [_location_out(r) for r in rows]


@router.post('/locations/ensure', response_model=LocationOut, status_code=status.HTTP_201_CREATED)
def ensure_location(payload: LocationEnsureIn, db: Session = Depends(get_db)):
    try:
        precision = LocationPrecisionLevel(payload.precision_level)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid precision_level') from exc

    country = payload.country.strip()
    region = payload.region.strip() if payload.region else None
    locality = payload.locality.strip()
    address_line = payload.address_line.strip() if payload.address_line else None
    entrance = payload.entrance.strip() if payload.entrance else None

    existing_stmt = select(Location).where(
        Location.country == country,
        Location.locality == locality,
        Location.precision_level == precision,
    )
    if region:
        existing_stmt = existing_stmt.where(Location.region == region)
    else:
        existing_stmt = existing_stmt.where(Location.region.is_(None))
    if address_line:
        existing_stmt = existing_stmt.where(Location.address_line == address_line)
    else:
        existing_stmt = existing_stmt.where(Location.address_line.is_(None))
    if entrance:
        existing_stmt = existing_stmt.where(Location.entrance == entrance)
    else:
        existing_stmt = existing_stmt.where(Location.entrance.is_(None))

    existing = db.execute(existing_stmt.limit(1)).scalar_one_or_none()
    if existing:
        return _location_out(existing)

    fallback = db.execute(
        select(Location)
        .where(Location.locality == locality)
        .order_by(Location.precision_level.asc())
        .limit(1)
    ).scalar_one_or_none()

    lat = payload.lat if payload.lat is not None else (float(fallback.lat) if fallback else None)
    lon = payload.lon if payload.lon is not None else (float(fallback.lon) if fallback else None)
    if lat is None or lon is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='lat and lon required for a new city')

    row = Location(
        country=country,
        region=region,
        locality=locality,
        address_line=address_line,
        entrance=entrance,
        postal_code=payload.postal_code,
        lat=Decimal(str(lat)),
        lon=Decimal(str(lon)),
        precision_level=precision,
        provider=LocationProvider.manual,
        provider_place_id=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _location_out(row)


@router.get('/locations/{location_id}', response_model=LocationOut)
def get_location(location_id: str, db: Session = Depends(get_db)):
    row = db.execute(select(Location).where(Location.id == location_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Location not found')
    return _location_out(row)


@router.post('/locations', response_model=LocationOut, status_code=status.HTTP_201_CREATED)
def create_location(payload: LocationIn, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        precision = LocationPrecisionLevel(payload.precision_level)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid precision_level')

    provider = None
    if payload.provider:
        try:
            provider = LocationProvider(payload.provider)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid provider')

    row = Location(
        country=payload.country.strip(),
        region=payload.region,
        locality=payload.locality.strip(),
        address_line=payload.address_line,
        entrance=payload.entrance,
        postal_code=payload.postal_code,
        lat=Decimal(str(payload.lat)),
        lon=Decimal(str(payload.lon)),
        precision_level=precision,
        provider=provider,
        provider_place_id=payload.provider_place_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _location_out(row)


@router.patch('/locations/{location_id}', response_model=LocationOut)
def update_location(location_id: str, payload: LocationIn, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(select(Location).where(Location.id == location_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Location not found')

    try:
        precision = LocationPrecisionLevel(payload.precision_level)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid precision_level')

    provider = None
    if payload.provider:
        try:
            provider = LocationProvider(payload.provider)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid provider')

    row.country = payload.country.strip()
    row.region = payload.region
    row.locality = payload.locality.strip()
    row.address_line = payload.address_line
    row.entrance = payload.entrance
    row.postal_code = payload.postal_code
    row.lat = Decimal(str(payload.lat))
    row.lon = Decimal(str(payload.lon))
    row.precision_level = precision
    row.provider = provider
    row.provider_place_id = payload.provider_place_id

    db.commit()
    db.refresh(row)
    return _location_out(row)


@router.delete('/locations/{location_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_location(location_id: str, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(select(Location).where(Location.id == location_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Location not found')
    db.delete(row)
    db.commit()
    return None


@router.get('/metro-stations', response_model=list[MetroStationOut])
def list_metro_stations(
    city_location_id: str | None = Query(default=None),
    near_location_id: str | None = Query(default=None),
    line_name: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(MetroStation)
    if city_location_id:
        stmt = stmt.where(MetroStation.city_location_id == city_location_id)
    if near_location_id:
        near = db.execute(select(Location).where(Location.id == near_location_id)).scalar_one_or_none()
        if near:
            city = aliased(Location)
            stmt = stmt.join(city, city.id == MetroStation.city_location_id).where(city.locality == near.locality)
    if line_name:
        stmt = stmt.where(MetroStation.line_name == line_name)
    if q:
        pattern = f'%{q.strip()}%'
        stmt = stmt.where(MetroStation.name.ilike(pattern) | MetroStation.line_name.ilike(pattern))
    rows = db.execute(stmt.order_by(MetroStation.line_name.asc(), MetroStation.name.asc())).scalars().all()
    return [_metro_out(r) for r in rows]


@router.get('/metro-stations/nearest', response_model=list[NearbyMetroStationOut])
def list_nearest_metro_stations(
    location_id: str = Query(...),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    location = db.execute(select(Location).where(Location.id == location_id)).scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Location not found')

    stmt = select(MetroStation).join(Location, Location.id == MetroStation.city_location_id).where(
        Location.locality == location.locality
    )

    rows = db.execute(stmt).scalars().all()
    rows = sorted(
        rows,
        key=lambda row: _distance_m(
            float(location.lat),
            float(location.lon),
            float(row.lat),
            float(row.lon),
        ),
    )[:limit]
    return [
        {
            **_metro_out(row),
            'distance_m': _distance_m(
                float(location.lat),
                float(location.lon),
                float(row.lat),
                float(row.lon),
            ),
        }
        for row in rows
    ]


@router.get('/metro-stations/nearest', response_model=list[NearbyMetroStationOut])
def list_nearest_metro_stations(
    location_id: str = Query(...),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    location = db.execute(select(Location).where(Location.id == location_id)).scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Location not found')

    stmt = select(MetroStation).join(Location, Location.id == MetroStation.city_location_id).where(
        Location.locality == location.locality
    )
    if location.region:
        stmt = stmt.where(Location.region == location.region)

    stations = db.execute(stmt).scalars().all()
    stations = sorted(
        stations,
        key=lambda row: _distance_m(float(location.lat), float(location.lon), float(row.lat), float(row.lon)),
    )[:limit]
    return [
        {
            **_metro_out(row),
            'distance_m': _distance_m(float(location.lat), float(location.lon), float(row.lat), float(row.lon)),
        }
        for row in stations
    ]


@router.post('/metro-stations', response_model=MetroStationOut, status_code=status.HTTP_201_CREATED)
def create_metro_station(payload: MetroStationIn, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = MetroStation(
        city_location_id=payload.city_location_id,
        name=payload.name.strip(),
        line_name=payload.line_name,
        lat=Decimal(str(payload.lat)),
        lon=Decimal(str(payload.lon)),
        color_hex=payload.color_hex,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        'id': str(row.id),
        'city_location_id': str(row.city_location_id),
        'name': row.name,
        'line_name': row.line_name,
        'lat': float(row.lat),
        'lon': float(row.lon),
        'color_hex': row.color_hex,
    }


@router.patch('/metro-stations/{station_id}', response_model=MetroStationOut)
def update_metro_station(station_id: str, payload: MetroStationIn, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(select(MetroStation).where(MetroStation.id == station_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Metro station not found')

    row.city_location_id = payload.city_location_id
    row.name = payload.name.strip()
    row.line_name = payload.line_name
    row.lat = Decimal(str(payload.lat))
    row.lon = Decimal(str(payload.lon))
    row.color_hex = payload.color_hex
    db.commit()
    db.refresh(row)
    return {
        'id': str(row.id),
        'city_location_id': str(row.city_location_id),
        'name': row.name,
        'line_name': row.line_name,
        'lat': float(row.lat),
        'lon': float(row.lon),
        'color_hex': row.color_hex,
    }


@router.delete('/metro-stations/{station_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_metro_station(station_id: str, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(select(MetroStation).where(MetroStation.id == station_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Metro station not found')
    db.delete(row)
    db.commit()
    return None


@router.get('/workplaces/me', response_model=list[MasterWorkplaceOut])
def list_my_workplaces(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.master:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only master can manage workplaces')
    rows = db.execute(
        select(MasterWorkplace, Location, MetroStation)
        .join(Location, Location.id == MasterWorkplace.location_id)
        .outerjoin(MetroStation, MetroStation.id == MasterWorkplace.public_metro_station_id)
        .where(MasterWorkplace.master_id == current_user.id)
        .order_by(MasterWorkplace.created_at.desc())
    ).all()
    return [_workplace_out(workplace, location, metro_station) for workplace, location, metro_station in rows]


@router.post('/workplaces/me', response_model=MasterWorkplaceOut, status_code=status.HTTP_201_CREATED)
def create_my_workplace(payload: MasterWorkplaceIn, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.master:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only master can manage workplaces')
    try:
        display_mode = WorkplaceDisplayMode(payload.public_display_mode)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid public_display_mode')

    if payload.is_primary:
        current_primary = db.execute(
            select(MasterWorkplace).where(
                MasterWorkplace.master_id == current_user.id,
                MasterWorkplace.is_primary.is_(True),
            )
        ).scalars().all()
        for row in current_primary:
            row.is_primary = False

    row = MasterWorkplace(
        master_id=current_user.id,
        location_id=payload.location_id,
        is_home_studio=payload.is_home_studio,
        studio_name=payload.studio_name,
        public_display_mode=display_mode,
        public_metro_station_id=payload.public_metro_station_id,
        public_text_override=payload.public_text_override,
        show_on_map=payload.show_on_map,
        public_lat=Decimal(str(payload.public_lat)) if payload.public_lat is not None else None,
        public_lon=Decimal(str(payload.public_lon)) if payload.public_lon is not None else None,
        is_primary=payload.is_primary,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    location = db.execute(select(Location).where(Location.id == row.location_id)).scalar_one_or_none()
    metro_station = db.execute(select(MetroStation).where(MetroStation.id == row.public_metro_station_id)).scalar_one_or_none() if row.public_metro_station_id else None
    return _workplace_out(row, location, metro_station)


@router.patch('/workplaces/me/{workplace_id}', response_model=MasterWorkplaceOut)
def update_my_workplace(
    workplace_id: str,
    payload: MasterWorkplaceIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.master:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only master can manage workplaces')

    row = db.execute(
        select(MasterWorkplace).where(
            MasterWorkplace.id == workplace_id,
            MasterWorkplace.master_id == current_user.id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Workplace not found')

    try:
        display_mode = WorkplaceDisplayMode(payload.public_display_mode)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid public_display_mode')

    if payload.is_primary:
        current_primary = db.execute(
            select(MasterWorkplace).where(
                MasterWorkplace.master_id == current_user.id,
                MasterWorkplace.is_primary.is_(True),
                MasterWorkplace.id != row.id,
            )
        ).scalars().all()
        for other in current_primary:
            other.is_primary = False

    row.location_id = payload.location_id
    row.is_home_studio = payload.is_home_studio
    row.studio_name = payload.studio_name
    row.public_display_mode = display_mode
    row.public_metro_station_id = payload.public_metro_station_id
    row.public_text_override = payload.public_text_override
    row.show_on_map = payload.show_on_map
    row.public_lat = Decimal(str(payload.public_lat)) if payload.public_lat is not None else None
    row.public_lon = Decimal(str(payload.public_lon)) if payload.public_lon is not None else None
    row.is_primary = payload.is_primary

    db.commit()
    db.refresh(row)
    location = db.execute(select(Location).where(Location.id == row.location_id)).scalar_one_or_none()
    metro_station = db.execute(select(MetroStation).where(MetroStation.id == row.public_metro_station_id)).scalar_one_or_none() if row.public_metro_station_id else None
    return _workplace_out(row, location, metro_station)


@router.delete('/workplaces/me/{workplace_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_my_workplace(workplace_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.master:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only master can manage workplaces')
    row = db.execute(
        select(MasterWorkplace).where(
            MasterWorkplace.id == workplace_id,
            MasterWorkplace.master_id == current_user.id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Workplace not found')
    db.delete(row)
    db.commit()
    return None
