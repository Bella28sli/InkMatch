from pydantic import BaseModel, Field


class CollectionListItemOut(BaseModel):
    id: str
    owner_id: str
    title: str
    description: str | None = None
    collection_type: str
    is_system: bool
    is_private: bool = False
    preview_url: str | None = None
    item_count: int = 0


class CollectionMediaItemOut(BaseModel):
    sketch_id: str
    media_url: str | None = None
    work_duration_houres: int | None = None
    work_price: int | None = None
    currency: str | None = None
    note: str | None = None


class CollectionOut(BaseModel):
    id: str
    owner_id: str
    title: str
    description: str | None = None
    collection_type: str
    is_system: bool
    is_private: bool = False
    media_urls: list[str]
    items: list[CollectionMediaItemOut]
    can_edit: bool


class CollectionCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    description: str | None = None
    collection_type: str = Field(default='custom')
    is_private: bool = False


class CollectionUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    is_private: bool | None = None


class CollectionItemIn(BaseModel):
    sketch_id: str
    sort_order: int | None = None
    work_duration_houres: int | None = Field(default=None, ge=0, le=1000)
    work_price: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=3)
    note: str | None = Field(default=None, max_length=500)


class CollectionItemUpdateIn(BaseModel):
    work_duration_houres: int | None = Field(default=None, ge=0, le=1000)
    work_price: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=3)
    note: str | None = Field(default=None, max_length=500)


class CollectionShareOut(BaseModel):
    share_url: str
