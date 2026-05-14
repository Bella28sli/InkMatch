from pydantic import BaseModel, Field


class DirectChatCreateIn(BaseModel):
    user_id: str


class ChatListItemOut(BaseModel):
    id: str
    chat_kind: str
    created_at: str
    other_user_id: str | None = None
    other_nickname: str | None = None
    other_avatar_url: str | None = None
    last_message_text: str | None = None
    last_message_at: str | None = None
    unread_count: int = 0


class MessageCreateIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class MessageAttachmentOut(BaseModel):
    id: str
    file_url: str
    file_type: str
    mime_type: str | None = None
    file_size_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: int | None = None


class MessageOut(BaseModel):
    id: str
    chat_id: str
    sender_id: str | None = None
    message_type: str
    text: str | None = None
    payload: dict | None = None
    created_at: str
    message_status: str | None = None
    attachments: list[MessageAttachmentOut] = Field(default_factory=list)
