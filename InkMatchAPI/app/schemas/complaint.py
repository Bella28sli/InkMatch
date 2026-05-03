from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ComplaintTargetType


class ComplaintReasonItemOut(BaseModel):
    code: str
    title: str
    description: str | None = None


class ComplaintReasonCategoryOut(BaseModel):
    code: str
    title: str
    reasons: list[ComplaintReasonItemOut]


class ComplaintCreateIn(BaseModel):
    target_type: ComplaintTargetType
    target_id: str
    reason_code: str
    details: str | None = Field(default=None, max_length=4000)


class ComplaintOut(BaseModel):
    id: str
    target_type: ComplaintTargetType
    target_id: str
    reason: str
    details: str | None = None
    status: str
    created_at: datetime
