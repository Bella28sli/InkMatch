from pydantic import BaseModel, Field


class InkmatchRequestCreateIn(BaseModel):
    sketch_id: str
    created_by_role: str


class InkmatchRequestUpdateIn(BaseModel):
    status: str


class InkmatchRequestOut(BaseModel):
    id: str
    created_by_user_id: str
    created_by_role: str
    sketch_id: str
    status: str
    created_at: str
    updated_at: str


class ClientInkmatchParamsIn(BaseModel):
    size_sm: int | None = None
    price_min: int | None = None
    price_max: int | None = None
    search_mode: str
    city_location_id: str | None = None
    region_location_id: str | None = None
    center_lat: float | None = None
    center_lon: float | None = None
    radius_meters: int | None = None
    preferred_experience_years_min: int | None = None
    preferred_rating_min: float | None = None
    preferred_workplace: str | None = None


class ClientInkmatchParamsOut(BaseModel):
    request_id: str
    size_sm: int | None = None
    price_min: int | None = None
    price_max: int | None = None
    search_mode: str
    city_location_id: str | None = None
    region_location_id: str | None = None
    center_lat: float | None = None
    center_lon: float | None = None
    radius_meters: int | None = None
    preferred_experience_years_min: int | None = None
    preferred_rating_min: float | None = None
    preferred_workplace: str | None = None


class MasterInkmatchOfferIn(BaseModel):
    offer_price: int = Field(ge=0)
    offer_duration_minutes: int = Field(ge=1)


class MasterInkmatchOfferOut(BaseModel):
    request_id: str
    offer_price: int
    offer_duration_minutes: int


class InkmatchCreateIn(BaseModel):
    sketch_id: str
    client_request_id: str
    master_request_id: str


class InkmatchOut(BaseModel):
    id: str
    sketch_id: str
    client_request_id: str
    master_request_id: str
    chat_id: str | None = None
    client_confirmed: bool = False
    master_confirmed: bool = False
    confirmed_at: str | None = None
    status: str
    created_at: str


class InkmatchReviewIn(BaseModel):
    inkmatch_id: str
    rating_overall: int = Field(ge=1, le=5)
    rating_communication: int = Field(ge=1, le=5)
    rating_cleanliness: int = Field(ge=1, le=5)
    rating_quality: int = Field(ge=1, le=5)
    rating_punctuality: int = Field(ge=1, le=5)
    rating_price_fairness: int = Field(ge=1, le=5)
    body: str | None = None


class InkmatchReviewOut(BaseModel):
    id: str
    inkmatch_id: str
    rating_overall: int
    rating_communication: int
    rating_cleanliness: int
    rating_quality: int
    rating_punctuality: int
    rating_price_fairness: int
    body: str | None = None
    created_at: str
    updated_at: str
