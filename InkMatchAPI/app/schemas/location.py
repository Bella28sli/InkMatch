from pydantic import BaseModel, Field


class LocationIn(BaseModel):
    country: str = Field(min_length=1, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    locality: str = Field(min_length=1, max_length=128)
    address_line: str | None = Field(default=None, max_length=255)
    entrance: str | None = Field(default=None, max_length=32)
    postal_code: str | None = Field(default=None, max_length=32)
    lat: float
    lon: float
    precision_level: str
    provider: str | None = None
    provider_place_id: str | None = Field(default=None, max_length=255)


class LocationEnsureIn(BaseModel):
    country: str = Field(default='Россия', min_length=1, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    locality: str = Field(min_length=1, max_length=128)
    address_line: str | None = Field(default=None, max_length=255)
    entrance: str | None = Field(default=None, max_length=32)
    postal_code: str | None = Field(default=None, max_length=32)
    lat: float | None = None
    lon: float | None = None
    precision_level: str = 'locality'


class LocationOut(BaseModel):
    id: str
    country: str
    region: str | None = None
    locality: str
    address_line: str | None = None
    entrance: str | None = None
    postal_code: str | None = None
    lat: float
    lon: float
    precision_level: str
    provider: str | None = None
    provider_place_id: str | None = None
    display_label: str | None = None
    short_label: str | None = None


class GeocodeCandidateOut(BaseModel):
    country: str | None = None
    region: str | None = None
    locality: str | None = None
    address_line: str | None = None
    entrance: str | None = None
    postal_code: str | None = None
    lat: float
    lon: float
    precision_level: str
    provider: str = 'yandex'
    provider_place_id: str | None = None
    display_label: str
    short_label: str | None = None


class MetroStationIn(BaseModel):
    city_location_id: str
    name: str = Field(min_length=1, max_length=128)
    line_name: str | None = Field(default=None, max_length=128)
    lat: float
    lon: float
    color_hex: str = Field(min_length=7, max_length=7)


class MetroStationOut(BaseModel):
    id: str
    city_location_id: str
    name: str
    line_name: str | None = None
    lat: float
    lon: float
    color_hex: str


class NearbyMetroStationOut(MetroStationOut):
    distance_m: int


class MasterWorkplaceIn(BaseModel):
    location_id: str
    is_home_studio: bool = True
    studio_name: str | None = Field(default=None, max_length=255)
    public_display_mode: str = 'street'
    public_metro_station_id: str | None = None
    public_text_override: str | None = Field(default=None, max_length=255)
    show_on_map: bool = True
    public_lat: float | None = None
    public_lon: float | None = None
    is_primary: bool = True


class MasterWorkplaceOut(BaseModel):
    id: str
    master_id: str
    location_id: str
    is_home_studio: bool
    studio_name: str | None = None
    public_display_mode: str
    public_metro_station_id: str | None = None
    public_text_override: str | None = None
    show_on_map: bool
    public_lat: float | None = None
    public_lon: float | None = None
    is_primary: bool
    location: LocationOut | None = None
    public_metro_station: MetroStationOut | None = None
    public_address: str | None = None
