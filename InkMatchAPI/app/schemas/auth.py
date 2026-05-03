from pydantic import BaseModel, EmailStr, Field, field_validator




def _validate_password_complexity(value: str) -> str:
    has_lower = any(ch.islower() for ch in value)
    has_upper = any(ch.isupper() for ch in value)
    if not has_lower or not has_upper:
        raise ValueError('Password must include lower and upper case letters')
    return value


class ProfileIn(BaseModel):
    nickname: str = Field(min_length=2, max_length=64)
    avatar_url: str | None = None
    bio: str | None = None
    home_location_id: str | None = None
    default_currency: str = Field(default="RUB", min_length=3, max_length=3)


class PreferencesIn(BaseModel):
    search_mode: str | None = None
    city_location_id: str | None = None
    region_location_id: str | None = None
    radius_meters: int | None = None
    center_lat: float | None = None
    center_lon: float | None = None
    preferred_experience_years_min: int | None = None
    preferred_rating_min: float | None = None
    preferred_workplace: str | None = None


class MasterProfileIn(BaseModel):
    experience_years: int | None = None
    price_min: int | None = None
    price_max: int | None = None
    description: str | None = None


class WorkplaceIn(BaseModel):
    location_id: str | None = None
    studio_name: str | None = None
    public_display_mode: str | None = None
    public_metro_station_id: str | None = None


class RegisterIn(BaseModel):
    email: EmailStr | None = None
    phone: str | None = None
    password: str = Field(min_length=8)
    role: str = Field(default="client")
    profile: ProfileIn
    preferred_style_ids: list[str] = Field(min_length=3, max_length=3)
    preferred_tag_ids: list[str] = Field(min_length=3, max_length=3)
    preferences: PreferencesIn | None = None
    master_profile: MasterProfileIn | None = None
    workplace: WorkplaceIn | None = None


    @field_validator('password')
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password_complexity(value)


class LoginIn(BaseModel):
    login: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_in: int


class RegisterOut(BaseModel):
    message: str


class RefreshIn(BaseModel):
    refresh_token: str


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)


    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return _validate_password_complexity(value)


class ResetRequestIn(BaseModel):
    email: EmailStr


class ResetConfirmIn(BaseModel):
    oob_code: str = Field(min_length=8)
    new_password: str = Field(min_length=8)


    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return _validate_password_complexity(value)


class VerifyRequestIn(BaseModel):
    login: str


class VerifyConfirmIn(BaseModel):
    login: str
    code: str


class NicknameCheckOut(BaseModel):
    available: bool
