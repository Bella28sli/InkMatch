from uuid import UUID

from pydantic import BaseModel, Field


class ProfileOut(BaseModel):
    user_id: UUID
    nickname: str
    avatar_url: str | None = None
    bio: str | None = None
    home_location_id: UUID | None = None
    default_currency: str

    class Config:
        from_attributes = True


class ProfileCreate(BaseModel):
    nickname: str = Field(min_length=2, max_length=64)
    avatar_url: str | None = None
    bio: str | None = None
    home_location_id: str | None = None
    default_currency: str = Field(default='RUB', min_length=3, max_length=3)


class ProfileUpdate(BaseModel):
    nickname: str | None = Field(default=None, min_length=2, max_length=64)
    avatar_url: str | None = None
    bio: str | None = None
    home_location_id: str | None = None
    default_currency: str | None = Field(default=None, min_length=3, max_length=3)


class ProfileFullOut(BaseModel):
    user_id: str
    role: str
    nickname: str
    avatar_url: str | None = None
    bio: str | None = None
    followers_count: int
    client_reviews_count: int
    master_rating: float | None = None
    master_completed_works: int | None = None
    master_address: str | None = None
    is_owner: bool
    is_verified: bool
    verification_skipped: bool = False
    is_favorite: bool

class MasterReviewAttachmentOut(BaseModel):
    id: str
    file_url: str
    file_type: str


class MasterReviewOut(BaseModel):
    id: str
    sketch_id: str
    reviewer_user_id: str
    reviewer_nickname: str | None = None
    reviewer_avatar_url: str | None = None
    rating_overall: int
    body: str | None = None
    created_at: str
    attachments: list[MasterReviewAttachmentOut] = []


class MasterFeedItemOut(BaseModel):
    user_id: str
    nickname: str
    avatar_url: str | None = None
    bio: str | None = None
    master_description: str | None = None
    master_address: str | None = None
    master_rating: float
    master_completed_works: int
    price_min: int | None = None
    price_max: int | None = None
    experience_years: int | None = None
    is_verified: bool
    is_favorite: bool
    followers_count: int
    preview_image_url: str | None = None
    is_subscribed: bool

