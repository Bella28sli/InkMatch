from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: str
    type: str
    title: str | None = None
    body: str | None = None
    is_read: bool
    image_url: str | None = None
    deep_link: str | None = None
    created_at: str


class PushTokenIn(BaseModel):
    platform: str
    token: str


class PushTokenDeleteIn(BaseModel):
    token: str
