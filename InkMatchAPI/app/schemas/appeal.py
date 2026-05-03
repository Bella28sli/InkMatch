from datetime import datetime

from pydantic import BaseModel, Field


class AppealAttachmentOut(BaseModel):
    id: str
    appeal_id: str
    file_url: str
    file_type: str
    created_at: datetime


class AppealCreateIn(BaseModel):
    target_type: str
    target_id: str
    description: str = Field(min_length=1, max_length=4000)
    reason_text: str | None = Field(default=None, max_length=2000)


class AppealOut(BaseModel):
    id: str
    appellant_user_id: str
    target_type: str
    target_id: str
    description: str
    status: str
    reason_text: str
    created_at: datetime
    updated_at: datetime
    reviewed_by_moderator_id: str | None = None
    reviewed_at: datetime | None = None
    decision_note: str | None = None
    attachments: list[AppealAttachmentOut] = Field(default_factory=list)
