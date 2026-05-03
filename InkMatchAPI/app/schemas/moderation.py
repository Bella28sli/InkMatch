from datetime import datetime

from pydantic import BaseModel, Field


class ModerationQueueItemOut(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    priority: int
    status: str
    assigned_moderator_id: str
    created_at: datetime
    entity_title: str | None = None
    entity_subtitle: str | None = None


class ModerationQueueTakeOut(BaseModel):
    id: str
    status: str
    assigned_moderator_id: str


class ModerationDecisionIn(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)
    reason_id: str | None = None
    block_author: bool = False
    favorite: bool = False


class ModerationDecisionOut(BaseModel):
    id: str
    status: str
    action: str


class ModerationQueueEntityOut(BaseModel):
    queue_id: str
    entity_type: str
    entity_id: str
    payload: dict


class ModerationUserStatsOut(BaseModel):
    followers_count: int
    following_count: int
    sketches_count: int
    collections_count: int
    comments_count: int
    likes_given_count: int
    chats_count: int
    messages_count: int
    complaints_authored_count: int
    complaints_against_count: int
    active_restrictions_count: int


class ModerationUserOut(BaseModel):
    id: str
    role: str
    email: str | None = None
    phone: str | None = None
    is_verified: bool
    is_favorite: bool = False
    profile: dict | None = None
    master_profile: dict | None = None
    stats: ModerationUserStatsOut


class ModerationDashboardStatsOut(BaseModel):
    queue_open: int
    queue_in_progress: int
    queue_done: int
    queue_complaints_open: int
    queue_new_posts_open: int
    complaints_open: int
    complaints_in_review: int
    complaints_resolved: int
    complaints_rejected: int
    active_restrictions: int
    actions_total: int

    posts_created: int
    users_registered: int
    chats_created: int
    messages_sent: int
    collections_created: int
    comments_created: int
    reviews_created: int
    avg_queue_priority: float
    avg_resolution_minutes: float


class ModerationUserListItemOut(BaseModel):
    id: str
    role: str
    email: str | None = None
    phone: str | None = None
    is_verified: bool
    is_favorite: bool = False
    nickname: str | None = None
    avatar_url: str | None = None


class ModerationTrendPointOut(BaseModel):
    period: str
    messages_sent: int
    comments_created: int
    complaints_created: int


class ModeratorProductivityOut(BaseModel):
    moderator_id: str
    nickname: str | None = None
    taken_count: int
    resolved_count: int
    approved_count: int
    rejected_count: int
    avg_resolution_minutes: float
    overdue_count: int


class ModerationStatsExtendedOut(ModerationDashboardStatsOut):
    trends: list[ModerationTrendPointOut]
    moderator_productivity: list[ModeratorProductivityOut]


class UserRestrictionOut(BaseModel):
    id: str
    user_id: str
    imposed_by_moderator_id: str
    restriction_type: str
    starts_at: datetime
    ends_at: datetime | None = None
    is_active: bool
    reason_id: str
    reason_title: str | None = None
    reason_description: str | None = None
    created_at: datetime


class UserRestrictionApplyIn(BaseModel):
    restriction_type: str
    reason: str | None = Field(default=None, max_length=2000)
    reason_id: str | None = None
    duration_hours: int | None = Field(default=None, ge=1, le=24 * 365)


class UserRestrictionDeactivateIn(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class ModerationReasonOut(BaseModel):
    id: str
    code: str
    title: str
    description: str | None = None
    applies_to: str
    priority: int
    is_active: bool


class ModerationReasonIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    applies_to: str = Field(default='general', min_length=1, max_length=64)
    priority: int = Field(default=5, ge=1, le=10)
    is_active: bool = True


class UserWarnIn(BaseModel):
    reason_id: str | None = None
    reason: str | None = Field(default=None, max_length=2000)


class UserWarnOut(BaseModel):
    user_id: str
    warnings_count: int
    requires_restriction: bool


class UserWarningOut(BaseModel):
    id: str
    user_id: str
    issued_by_moderator_id: str
    reason_id: str | None = None
    reason_title: str | None = None
    reason_text: str
    status: str
    related_restriction_id: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None
