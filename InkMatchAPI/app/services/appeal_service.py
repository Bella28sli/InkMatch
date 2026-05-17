from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import (
    AppealStatus,
    AppealTargetType,
    ComplaintTargetType,
    FileType,
    ModerationActionType,
    ModerationQueueEntityType,
    ModerationQueueStatus,
    NotificationType,
    UserRole,
)
from app.models.moderation import Appeal, AppealAttachment, ModerationAction, ModerationQueueItem
from app.models.messaging import MessageAttachment
from app.models.sketches import SketchComment, SketchMedia
from app.models.user import User
from app.models.user_extras import UserRestriction
from app.services.notification_service import create_notification, push_icon_url
from app.services.media_service import resolve_media_url
from app.services.restriction_service import deactivate_user_restriction


APPEAL_PRIORITY = 3


def _to_uuid(raw: str) -> UUID | None:
    try:
        return UUID(str(raw))
    except (TypeError, ValueError):
        return None


def _appeal_image_url(db: Session, appeal: Appeal) -> str | None:
    if appeal.target_type == AppealTargetType.sketch:
        raw = db.execute(
            select(SketchMedia.url)
            .where(SketchMedia.sketch_id == appeal.target_id)
            .order_by(SketchMedia.sort_order.asc())
            .limit(1)
        ).scalar_one_or_none()
        return resolve_media_url(raw) if raw else None
    if appeal.target_type == AppealTargetType.message:
        attachment = db.execute(
            select(MessageAttachment)
            .where(MessageAttachment.message_id == appeal.target_id)
            .order_by(MessageAttachment.created_at.asc())
            .limit(1)
        ).scalar_one_or_none()
        if attachment and attachment.file_type == FileType.image:
            return resolve_media_url(attachment.file_url)
    if appeal.target_type == AppealTargetType.complaint:
        return None
    comment = db.execute(select(SketchComment).where(SketchComment.id == appeal.target_id)).scalar_one_or_none()
    if comment:
        raw = db.execute(
            select(SketchMedia.url)
            .where(SketchMedia.sketch_id == comment.sketch_id)
            .order_by(SketchMedia.sort_order.asc())
            .limit(1)
        ).scalar_one_or_none()
        return resolve_media_url(raw) if raw else None
    return None


def _first_moderator_id(db: Session) -> UUID | None:
    return db.execute(
        select(User.id).where(User.role == UserRole.moderator).order_by(User.id.asc()).limit(1)
    ).scalar_one_or_none()


def _appeal_out(row: Appeal) -> dict:
    return {
        'id': str(row.id),
        'appellant_user_id': str(row.appellant_user_id),
        'target_type': row.target_type.value,
        'target_id': str(row.target_id),
        'description': row.description,
        'status': row.status.value,
        'reason_text': row.reason_text,
        'created_at': row.created_at,
        'updated_at': row.updated_at,
        'reviewed_by_moderator_id': str(row.reviewed_by_moderator_id) if row.reviewed_by_moderator_id else None,
        'reviewed_at': row.reviewed_at,
        'decision_note': row.decision_note,
        'attachments': [],
    }


def _attachment_out(row: AppealAttachment) -> dict:
    return {
        'id': str(row.id),
        'appeal_id': str(row.appeal_id),
        'file_url': resolve_media_url(row.file_url),
        'file_type': row.file_type.value,
        'created_at': row.created_at,
    }


def list_my_appeals(db: Session, user_id: str) -> list[dict]:
    user_uuid = _to_uuid(user_id)
    if not user_uuid:
        return []
    rows = db.execute(
        select(Appeal)
        .where(Appeal.appellant_user_id == user_uuid)
        .order_by(Appeal.created_at.desc())
    ).scalars().all()
    payload = [_appeal_out(row) for row in rows]
    if not rows:
        return payload
    attachment_rows = db.execute(
        select(AppealAttachment)
        .where(AppealAttachment.appeal_id.in_([row.id for row in rows]))
        .order_by(AppealAttachment.created_at.asc())
    ).scalars().all()
    by_appeal: dict[str, list[dict]] = {}
    for attachment in attachment_rows:
        by_appeal.setdefault(str(attachment.appeal_id), []).append(_attachment_out(attachment))
    for item in payload:
        item['attachments'] = by_appeal.get(item['id'], [])
    return payload


def create_appeal(
    db: Session,
    *,
    user_id: str,
    target_type: AppealTargetType,
    target_id: str,
    description: str,
    reason_text: str | None = None,
) -> Appeal | None:
    user_uuid = _to_uuid(user_id)
    target_uuid = _to_uuid(target_id)
    moderator_uuid = _first_moderator_id(db)
    if not user_uuid or not target_uuid or not moderator_uuid:
        return None

    if target_type == AppealTargetType.user_restriction:
        restriction = db.execute(select(UserRestriction).where(UserRestriction.id == target_uuid)).scalar_one_or_none()
        if not restriction or str(restriction.user_id) != str(user_uuid):
            return None

    existing = db.execute(
        select(Appeal).where(
            Appeal.appellant_user_id == user_uuid,
            Appeal.target_type == target_type,
            Appeal.target_id == target_uuid,
            Appeal.status.in_([AppealStatus.submitted, AppealStatus.in_review]),
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    row = Appeal(
        appellant_user_id=user_uuid,
        target_type=target_type,
        target_id=target_uuid,
        description=description.strip(),
        reason_text=(reason_text or description).strip(),
        status=AppealStatus.submitted,
    )
    db.add(row)
    db.flush()
    db.add(
        ModerationQueueItem(
            entity_type=ModerationQueueEntityType.appeal,
            entity_id=row.id,
            priority=APPEAL_PRIORITY,
            status=ModerationQueueStatus.open,
            assigned_moderator_id=moderator_uuid,
        )
    )
    db.flush()
    return row


def approve_appeal(db: Session, *, appeal: Appeal, moderator_id: str, note: str | None = None) -> None:
    appeal.status = AppealStatus.approved
    appeal.reviewed_by_moderator_id = _to_uuid(moderator_id)
    appeal.reviewed_at = datetime.now(timezone.utc)
    appeal.decision_note = note
    if appeal.target_type == AppealTargetType.user_restriction:
        deactivate_user_restriction(
            db,
            restriction_id=str(appeal.target_id),
            moderator_id=moderator_id,
            reason=note or 'Апелляция одобрена',
        )
    else:
        db.add(
            ModerationAction(
                moderator_id=_to_uuid(moderator_id),
                action_type=ModerationActionType.restore_content,
                target_type=ComplaintTargetType.user,
                target_id=appeal.appellant_user_id,
                reason=note or 'Апелляция одобрена',
                params={'appeal_id': str(appeal.id), 'target_type': appeal.target_type.value},
            )
        )
    create_notification(
        db,
        user_id=str(appeal.appellant_user_id),
        type_=NotificationType.moderation,
        title='Апелляция одобрена',
        body=note or 'Модератор одобрил вашу апелляцию.',
        deep_link='/account/restrictions',
        image_url=_appeal_image_url(db, appeal) or push_icon_url('verification'),
        links=[('appeal', str(appeal.id))],
        send_push_too=True,
        in_app=True,
    )


def reject_appeal(db: Session, *, appeal: Appeal, moderator_id: str, note: str | None = None) -> None:
    appeal.status = AppealStatus.rejected
    appeal.reviewed_by_moderator_id = _to_uuid(moderator_id)
    appeal.reviewed_at = datetime.now(timezone.utc)
    appeal.decision_note = note
    db.add(
        ModerationAction(
            moderator_id=_to_uuid(moderator_id),
            action_type=ModerationActionType.resolve_complaint,
            target_type=ComplaintTargetType.user,
            target_id=appeal.appellant_user_id,
            reason=note or 'Апелляция отклонена',
            params={'appeal_id': str(appeal.id), 'target_type': appeal.target_type.value},
        )
    )
    create_notification(
        db,
        user_id=str(appeal.appellant_user_id),
        type_=NotificationType.moderation,
        title='Апелляция отклонена',
        body=note or 'Модератор отклонил вашу апелляцию.',
        deep_link='/account/restrictions',
        image_url=_appeal_image_url(db, appeal) or push_icon_url('complaint'),
        links=[('appeal', str(appeal.id))],
        send_push_too=True,
        in_app=True,
    )


def serialize_appeal(row: Appeal) -> dict:
    return _appeal_out(row)


def add_appeal_attachment(
    db: Session,
    *,
    appeal_id: str,
    user_id: str,
    file_url: str,
    file_type: FileType,
) -> AppealAttachment | None:
    appeal_uuid = _to_uuid(appeal_id)
    user_uuid = _to_uuid(user_id)
    if not appeal_uuid or not user_uuid:
        return None
    appeal = db.execute(select(Appeal).where(Appeal.id == appeal_uuid)).scalar_one_or_none()
    if not appeal or str(appeal.appellant_user_id) != str(user_uuid):
        return None
    if appeal.status not in {AppealStatus.submitted, AppealStatus.in_review}:
        return None
    row = AppealAttachment(appeal_id=appeal_uuid, file_url=file_url, file_type=file_type)
    db.add(row)
    db.flush()
    return row


def list_appeal_attachments(db: Session, *, appeal_id: str, user_id: str | None = None) -> list[dict]:
    appeal_uuid = _to_uuid(appeal_id)
    if not appeal_uuid:
        return []
    if user_id is not None:
        user_uuid = _to_uuid(user_id)
        if not user_uuid:
            return []
        appeal = db.execute(select(Appeal).where(Appeal.id == appeal_uuid)).scalar_one_or_none()
        if not appeal or str(appeal.appellant_user_id) != str(user_uuid):
            return []
    rows = db.execute(
        select(AppealAttachment)
        .where(AppealAttachment.appeal_id == appeal_uuid)
        .order_by(AppealAttachment.created_at.asc())
    ).scalars().all()
    return [_attachment_out(row) for row in rows]


def serialize_appeal_attachment(row: AppealAttachment) -> dict:
    return _attachment_out(row)
