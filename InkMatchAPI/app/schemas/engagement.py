from pydantic import BaseModel, Field


class FileAttachmentIn(BaseModel):
    file_url: str = Field(min_length=1, max_length=512)
    file_type: str = Field(min_length=1, max_length=32)
    mime_type: str | None = Field(default=None, max_length=128)
    file_size_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: int | None = None


class FileAttachmentOut(BaseModel):
    id: str
    file_url: str
    file_type: str
    mime_type: str | None = None
    file_size_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: int | None = None


class NotificationLinkIn(BaseModel):
    entity_type: str = Field(min_length=1, max_length=64)
    entity_id: str


class NotificationLinkOut(BaseModel):
    id: str
    notification_id: str
    entity_type: str
    entity_id: str


class PinIn(BaseModel):
    comment_id: str
    pinned_reason: str = Field(default='inkmatch_review', max_length=64)


class PinOut(BaseModel):
    sketch_id: str
    pinned_comment_id: str
    pinned_by_user_id: str
    pinned_reason: str


class CommentLikeOut(BaseModel):
    comment_id: str
    likes_count: int
    is_liked: bool
