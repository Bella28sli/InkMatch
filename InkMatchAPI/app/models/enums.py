from enum import Enum


class UserRole(str, Enum):
    client = "client"
    master = "master"
    moderator = "moderator"


class SketchContentType(str, Enum):
    sketch = "sketch"
    final_work = "final_work"
    process = "process"
    portfolio = "portfolio"
    achievments = "achievments"
    find_us = "find_us"
    materials = "materials"


class OriginalAuthorType(str, Enum):
    self_ = "self"
    other = "other"
    unknown = "unknown"


class WorkplaceDisplayMode(str, Enum):
    city_only = "city_only"
    street = "street"
    metro = "metro"
    full_address = "full_address"


class MediaType(str, Enum):
    image = "image"
    video = "video"


class AppealTargetType(str, Enum):
    moderation_action = "moderation_action"
    user_restriction = "user_restriction"
    complaint = "complaint"
    sketch = "sketch"
    message = "message"


class AppealStatus(str, Enum):
    submitted = "submitted"
    in_review = "in_review"
    approved = "approved"
    rejected = "rejected"
    closed = "closed"


class DocumentType(str, Enum):
    id = "id"
    passport = "passport"
    certificate = "certificate"
    diploma = "diploma"
    award = "award"
    other = "other"


class SearchMode(str, Enum):
    city = "city"
    region = "region"
    radius = "radius"


class WorkplaceType(str, Enum):
    studio = "studio"
    home = "home"
    any = "any"


class RestrictionType(str, Enum):
    full_block = "full_block"
    chat_only_read = "chat_only_read"
    posting_disabled = "posting_disabled"
    commenting_disabled = "commenting_disabled"
    inkmatch_disabled = "inkmatch_disabled"
    profile_hidden = "profile_hidden"


class ModerationQueueEntityType(str, Enum):
    complaint = "complaint"
    verification = "verification"
    new_post = "new_post"
    message_report = "message_report"
    appeal = "appeal"
    suspicious_case = "suspicious_case"


class ModerationQueueStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    done = "done"


class FileType(str, Enum):
    image = "image"
    video = "video"
    document = "document"
    other = "other"


class CollectionType(str, Enum):
    portfolio = "portfolio"
    materials = "materials"
    process = "process"
    find_us = "find_us"
    achievments = "achievments"
    likes = "likes"
    custom = "custom"


class InkmatchStatus(str, Enum):
    active = "active"
    archived = "archived"
    cancelled = "cancelled"


class InkmatchRequestStatus(str, Enum):
    active = "active"
    paused = "paused"
    matched = "matched"
    cancelled = "cancelled"
    deleted = "deleted"


class RequestCreatorRole(str, Enum):
    client = "client"
    master = "master"


class NotificationType(str, Enum):
    message = "message"
    inkmatch = "inkmatch"
    session = "session"
    moderation = "moderation"
    system = "system"


class ChatKind(str, Enum):
    direct = "direct"


class ComplaintTargetType(str, Enum):
    user = "user"
    sketch = "sketch"
    message = "message"
    comment = "comment"
    review = "review"


class ComplaintStatus(str, Enum):
    open = "open"
    in_review = "in_review"
    resolved = "resolved"
    rejected = "rejected"


class ModerationActionType(str, Enum):
    warn = "warn"
    block_user = "block_user"
    apply_restriction = "apply_restriction"
    remove_content = "remove_content"
    restore_content = "restore_content"
    resolve_complaint = "resolve_complaint"


class LocationPrecisionLevel(str, Enum):
    exact = "exact"
    locality = "locality"
    region = "region"


class LocationProvider(str, Enum):
    yandex = "yandex"
    dadata = "dadata"
    osm = "osm"
    manual = "manual"


class VerificationStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"
    in_review = "in_review"
    approved = "approved"
    rejected = "rejected"
    skipped = "skipped"


class AuditSource(str, Enum):
    mobile = "mobile"
    web = "web"
    admin = "admin"
    system = "system"
