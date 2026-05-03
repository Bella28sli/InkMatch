from pydantic import BaseModel, Field


class SketchMediaCreateIn(BaseModel):
    url: str
    phash: str | None = Field(default=None, max_length=16)


class SketchCreateIn(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    content_type: str
    feed_visibility: str = Field(default='public', max_length=32)
    media_urls: list[str] = Field(default_factory=list)
    media_items: list[SketchMediaCreateIn] = Field(default_factory=list)
    collection_id: str | None = None


class SketchUpdateIn(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    feed_visibility: str | None = Field(default=None, max_length=32)


class SketchListItemOut(BaseModel):
    id: str
    author_id: str
    title: str | None = None
    description: str | None = None
    content_type: str
    feed_visibility: str
    created_at: str
    like_amount: int
    preview_url: str | None = None


class SketchDetailOut(BaseModel):
    id: str
    author_id: str
    title: str | None = None
    description: str | None = None
    content_type: str
    feed_visibility: str
    created_at: str
    updated_at: str
    like_amount: int
    media_urls: list[str]


class SketchRefsIn(BaseModel):
    ids: list[str] = Field(default_factory=list)
