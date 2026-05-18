from pydantic import BaseModel, Field


class AccountOut(BaseModel):
    id: str
    email: str | None = None
    phone: str | None = None
    role: str
    is_verified: bool


class AccountUpdateIn(BaseModel):
    email: str | None = None
    phone: str | None = None


class ChangePasswordIn(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class BindEmailRequestIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class BindEmailConfirmIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    oob_code: str = Field(min_length=6, max_length=64)


class MasterProfileIn(BaseModel):
    experience_years: int | None = None
    price_min: int | None = None
    price_max: int | None = None
    description: str | None = None


class MasterProfileOut(BaseModel):
    user_id: str
    experience_years: int | None = None
    price_min: int | None = None
    price_max: int | None = None
    description: str | None = None
    is_verified: bool
    rating_avg: float
    completed_sessions_count: int


class InkmatchDefaultsIn(BaseModel):
    experience_years_min: int | None = None
    rating_min: float | None = None
    workplace: str | None = None
    search_mode: str = 'city'
    city_location_id: str | None = None
    region_location_id: str | None = None
    radius_meters: int | None = None
    center_lat: float | None = None
    center_lon: float | None = None
    default_size_sm: int | None = None
    default_price_min: int | None = None
    default_price_max: int | None = None


class InkmatchDefaultsOut(BaseModel):
    user_id: str
    experience_years_min: int | None = None
    rating_min: float | None = None
    workplace: str | None = None
    search_mode: str
    city_location_id: str | None = None
    region_location_id: str | None = None
    radius_meters: int | None = None
    center_lat: float | None = None
    center_lon: float | None = None
    default_size_sm: int | None = None
    default_price_min: int | None = None
    default_price_max: int | None = None


class FeedPreferenceWeightIn(BaseModel):
    id: str
    weight: int = Field(ge=-10, le=10)


class FeedPreferenceWeightOut(BaseModel):
    id: str
    weight: int


class FeedPreferenceIn(BaseModel):
    style_weights: list[FeedPreferenceWeightIn] = Field(default_factory=list)
    tag_weights: list[FeedPreferenceWeightIn] = Field(default_factory=list)


class FeedPreferenceOut(BaseModel):
    user_id: str
    style_weights: list[FeedPreferenceWeightOut]
    tag_weights: list[FeedPreferenceWeightOut]
