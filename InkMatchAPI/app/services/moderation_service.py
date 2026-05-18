from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import (
    ComplaintStatus,
    ComplaintTargetType,
    ModerationActionType,
    ModerationQueueEntityType,
    ModerationQueueStatus,
    NotificationType,
    RestrictionType,
    UserRole,
    VerificationStatus,
    AppealStatus,
)
from app.models.inkmatch import Inkmatch, InkmatchRequest, InkmatchReview
from app.models.messaging import Chat, ChatParticipant, Message, MessageAttachment
from app.models.moderation import Appeal, AppealAttachment, Complaint, ModerationAction, ModerationQueueItem, ModerationReason, UserWarning
from app.models.profiles import MasterProfile, Profile
from app.models.verification import (
    MasterVerificationDocument,
    MasterVerificationDocumentFile,
    MasterVerificationPersonalData,
    MasterVerificationRequest,
)
from app.models.sketches import (
    Collection,
    CollectionItem,
    CommentAttachment,
    Sketch,
    SketchComment,
    SketchCommentLike,
    SketchLike,
    SketchMedia,
    SketchPin,
    SketchStyle,
    SketchTag,
)
from app.models.user import User
from app.models.user_extras import Subscription, UserRestriction
from app.services.complaint_service import resolve_target_owner_user_id, resolve_target_preview_image_url
from app.services.media_service import resolve_media_url
from app.services.notification_service import create_notification
from app.services.appeal_service import approve_appeal, reject_appeal


DEFAULT_NEW_POST_PRIORITY = 10


def _to_uuid(raw: str) -> UUID | None:
    try:
        return UUID(raw)
    except (TypeError, ValueError):
        return None


def _count(db: Session, stmt) -> int:
    return int(db.execute(stmt).scalar_one() or 0)


def _first_moderator_id(db: Session) -> str | None:
    row = db.execute(
        select(User.id).where(User.role == UserRole.moderator).order_by(User.id.asc()).limit(1)
    ).scalar_one_or_none()
    return str(row) if row else None


def _priority_for_reason_code(db: Session, reason_code: str) -> int:
    priority = db.execute(
        select(ModerationReason.priority)
        .where(
            ModerationReason.code == reason_code,
            ModerationReason.is_active.is_(True),
        )
        .order_by(ModerationReason.priority.asc())
        .limit(1)
    ).scalar_one_or_none()
    if priority is None:
        return 6
    return int(priority)


def enqueue_new_post_for_moderation(db: Session, sketch_id: str) -> ModerationQueueItem | None:
    sketch_uuid = _to_uuid(sketch_id)
    if not sketch_uuid:
        return None

    existing = db.execute(
        select(ModerationQueueItem).where(
            ModerationQueueItem.entity_type == ModerationQueueEntityType.new_post,
            ModerationQueueItem.entity_id == sketch_uuid,
            ModerationQueueItem.status.in_([ModerationQueueStatus.open, ModerationQueueStatus.in_progress]),
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    moderator_uuid = None
    moderator_id = _first_moderator_id(db)
    if moderator_id:
        moderator_uuid = _to_uuid(moderator_id)

    row = ModerationQueueItem(
        entity_type=ModerationQueueEntityType.new_post,
        entity_id=sketch_uuid,
        priority=DEFAULT_NEW_POST_PRIORITY,
        status=ModerationQueueStatus.open,
        assigned_moderator_id=moderator_uuid,
    )
    db.add(row)
    db.flush()
    return row


def enqueue_complaint_for_moderation(db: Session, complaint_id: str, reason_code: str) -> ModerationQueueItem | None:
    complaint_uuid = _to_uuid(complaint_id)
    if not complaint_uuid:
        return None

    complaint = db.execute(select(Complaint).where(Complaint.id == complaint_uuid)).scalar_one_or_none()
    entity_type = (
        ModerationQueueEntityType.message_report
        if complaint and complaint.target_type == ComplaintTargetType.message
        else ModerationQueueEntityType.complaint
    )

    existing = db.execute(
        select(ModerationQueueItem).where(
            ModerationQueueItem.entity_type == entity_type,
            ModerationQueueItem.entity_id == complaint_uuid,
            ModerationQueueItem.status.in_([ModerationQueueStatus.open, ModerationQueueStatus.in_progress]),
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    moderator_uuid = None
    moderator_id = _first_moderator_id(db)
    if moderator_id:
        moderator_uuid = _to_uuid(moderator_id)

    row = ModerationQueueItem(
        entity_type=entity_type,
        entity_id=complaint_uuid,
        priority=1,
        status=ModerationQueueStatus.open,
        assigned_moderator_id=moderator_uuid,
    )
    db.add(row)
    db.flush()
    return row


def list_queue_items(
    db: Session,
    *,
    moderator_id: str,
    status_filter: ModerationQueueStatus | None,
    limit: int,
    offset: int,
) -> list[dict]:
    moderator_uuid = _to_uuid(moderator_id)
    if not moderator_uuid:
        return []

    stmt = select(ModerationQueueItem)
    if status_filter:
        stmt = stmt.where(ModerationQueueItem.status == status_filter)

    rows = db.execute(
        stmt.order_by(ModerationQueueItem.priority.asc(), ModerationQueueItem.created_at.asc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()

    result: list[dict] = []
    for row in rows:
        title = None
        subtitle = None
        result_preview = None

        if row.entity_type == ModerationQueueEntityType.new_post:
            sketch = db.execute(select(Sketch).where(Sketch.id == row.entity_id)).scalar_one_or_none()
            if sketch:
                author = db.execute(select(Profile.nickname).where(Profile.user_id == sketch.author_id)).scalar_one_or_none()
                first_media = db.execute(
                    select(SketchMedia).where(SketchMedia.sketch_id == sketch.id).order_by(SketchMedia.sort_order.asc())
                ).scalars().first()
                title = sketch.title or 'Untitled post'
                subtitle = f'author: {author or str(sketch.author_id)}'
                result_preview = {
                    'kind': 'sketch',
                    'title': sketch.title,
                    'description': sketch.description,
                    'image_url': resolve_media_url(first_media.url) if first_media else None,
                    'author_nickname': author,
                }
        elif row.entity_type in {ModerationQueueEntityType.complaint, ModerationQueueEntityType.message_report}:
            complaint = db.execute(select(Complaint).where(Complaint.id == row.entity_id)).scalar_one_or_none()
            if complaint:
                title = f'Complaint: {complaint.target_type.value}'
                subtitle = complaint.reason
                if complaint.target_type == ComplaintTargetType.sketch:
                    sketch = db.execute(select(Sketch).where(Sketch.id == complaint.target_id)).scalar_one_or_none()
                    if sketch:
                        first_media = db.execute(
                            select(SketchMedia).where(SketchMedia.sketch_id == sketch.id).order_by(SketchMedia.sort_order.asc())
                        ).scalars().first()
                        result_preview = {
                            'kind': 'sketch',
                            'title': sketch.title,
                            'description': sketch.description,
                            'image_url': resolve_media_url(first_media.url) if first_media else None,
                        }
                elif complaint.target_type == ComplaintTargetType.comment:
                    comment = db.execute(select(SketchComment).where(SketchComment.id == complaint.target_id)).scalar_one_or_none()
                    if comment:
                        result_preview = {
                            'kind': 'comment',
                            'text': comment.body,
                            'sketch_id': str(comment.sketch_id),
                            'image_url': None,
                        }
                elif complaint.target_type == ComplaintTargetType.message:
                    message = db.execute(select(Message).where(Message.id == complaint.target_id)).scalar_one_or_none()
                    if message:
                        attachment = db.execute(
                            select(MessageAttachment).where(MessageAttachment.message_id == message.id).order_by(MessageAttachment.created_at.asc())
                        ).scalars().first()
                        result_preview = {
                            'kind': 'message',
                            'text': message.text,
                            'attachment_url': resolve_media_url(attachment.file_url) if attachment else None,
                            'image_url': None,
                        }
        elif row.entity_type == ModerationQueueEntityType.suspicious_case:
            complaint = db.execute(select(Complaint).where(Complaint.id == row.entity_id)).scalar_one_or_none()
            if complaint:
                related_count = _count(
                    db,
                    select(func.count()).select_from(Complaint).where(
                        Complaint.target_type == complaint.target_type,
                        Complaint.target_id == complaint.target_id,
                    ),
                )
                title = f'Suspicious case: {complaint.target_type.value}'
                subtitle = f'{related_count} complaints for one target'
                result_preview = {}
                if complaint.target_type == ComplaintTargetType.sketch:
                    sketch = db.execute(select(Sketch).where(Sketch.id == complaint.target_id)).scalar_one_or_none()
                    if sketch:
                        first_media = db.execute(
                            select(SketchMedia).where(SketchMedia.sketch_id == sketch.id).order_by(SketchMedia.sort_order.asc())
                        ).scalars().first()
                        result_preview = {
                            'kind': 'sketch',
                            'title': sketch.title,
                            'description': sketch.description,
                            'image_url': resolve_media_url(first_media.url) if first_media else None,
                        }
                elif complaint.target_type == ComplaintTargetType.comment:
                    comment = db.execute(select(SketchComment).where(SketchComment.id == complaint.target_id)).scalar_one_or_none()
                    if comment:
                        result_preview = {
                            'kind': 'comment',
                            'text': comment.body,
                            'sketch_id': str(comment.sketch_id),
                            'image_url': None,
                        }
                elif complaint.target_type == ComplaintTargetType.message:
                    message = db.execute(select(Message).where(Message.id == complaint.target_id)).scalar_one_or_none()
                    if message:
                        attachment = db.execute(
                            select(MessageAttachment).where(MessageAttachment.message_id == message.id).order_by(MessageAttachment.created_at.asc())
                        ).scalars().first()
                        result_preview = {
                            'kind': 'message',
                            'text': message.text,
                            'attachment_url': resolve_media_url(attachment.file_url) if attachment else None,
                            'image_url': None,
                        }
        elif row.entity_type == ModerationQueueEntityType.verification:
            request = db.execute(select(MasterVerificationRequest).where(MasterVerificationRequest.id == row.entity_id)).scalar_one_or_none()
            if request:
                user_nickname = db.execute(
                    select(Profile.nickname).where(Profile.user_id == request.master_id)
                ).scalar_one_or_none()
                title = 'Verification request'
                subtitle = f'master: {user_nickname or str(request.master_id)} | status: {request.status.value}'
        elif row.entity_type == ModerationQueueEntityType.appeal:
            appeal = db.execute(select(Appeal).where(Appeal.id == row.entity_id)).scalar_one_or_none()
            if appeal:
                title = 'Appeal'
                subtitle = f'{appeal.target_type.value} | {appeal.status.value}'

        result.append(
            {
                'id': str(row.id),
                'entity_type': row.entity_type.value,
                'entity_id': str(row.entity_id),
                'priority': int(row.priority),
                'status': row.status.value,
                'assigned_moderator_id': str(row.assigned_moderator_id) if row.assigned_moderator_id else None,
                'created_at': row.created_at,
                'entity_title': title,
                'entity_subtitle': subtitle,
                'entity_preview': result_preview,
            }
        )
    return result


def get_queue_item_entity(db: Session, *, queue_id: str) -> dict | None:
    queue_uuid = _to_uuid(queue_id)
    if not queue_uuid:
        return None

    row = db.execute(select(ModerationQueueItem).where(ModerationQueueItem.id == queue_uuid)).scalar_one_or_none()
    if not row:
        return None

    payload: dict = {}
    if row.entity_type == ModerationQueueEntityType.new_post:
        sketch = db.execute(select(Sketch).where(Sketch.id == row.entity_id)).scalar_one_or_none()
        if sketch:
            author_nickname = db.execute(
                select(Profile.nickname).where(Profile.user_id == sketch.author_id)
            ).scalar_one_or_none()
            first_media = db.execute(
                select(SketchMedia).where(SketchMedia.sketch_id == sketch.id).order_by(SketchMedia.sort_order.asc())
            ).scalars().first()
            payload = {
                'id': str(sketch.id),
                'title': sketch.title,
                'description': sketch.description,
                'content_type': sketch.content_type.value,
                'feed_visibility': sketch.feed_visibility,
                'reviewed': bool(sketch.reviewed),
                'author_id': str(sketch.author_id),
                'author_nickname': author_nickname,
                'image_url': resolve_media_url(first_media.url) if first_media else None,
                'created_at': sketch.created_at,
            }
    elif row.entity_type == ModerationQueueEntityType.verification:
        request = db.execute(select(MasterVerificationRequest).where(MasterVerificationRequest.id == row.entity_id)).scalar_one_or_none()
        if request:
            personal_data = db.execute(
                select(MasterVerificationPersonalData)
                .where(MasterVerificationPersonalData.request_id == request.id)
            ).scalar_one_or_none()
            documents = []
            attachments = db.execute(
                select(MasterVerificationDocumentFile, MasterVerificationDocument)
                .join(MasterVerificationDocument, MasterVerificationDocument.id == MasterVerificationDocumentFile.document_id)
                .where(MasterVerificationDocument.request_id == request.id)
                .order_by(MasterVerificationDocument.created_at.asc(), MasterVerificationDocumentFile.created_at.asc())
            ).all()
            for file_row, document_row in attachments:
                documents.append(
                    {
                        'id': str(file_row.id),
                        'document_id': str(document_row.id),
                        'document_type': document_row.document_type.value,
                        'title': document_row.title,
                        'issuer': document_row.issuer,
                        'issued_date': document_row.issued_date.isoformat() if document_row.issued_date else None,
                        'file_url': resolve_media_url(file_row.file_url),
                        'file_type': file_row.file_type,
                        'created_at': file_row.created_at.isoformat(),
                    }
                )
            payload = {
                'request_id': str(request.id),
                'master_id': str(request.master_id),
                'status': request.status.value,
                'comments': request.comments,
                'rejection_reason': request.rejection_reason,
                'submitted_at': request.submitted_at.isoformat() if request.submitted_at else None,
                'reviewed_at': request.reviewed_at.isoformat() if request.reviewed_at else None,
                'personal_data': {
                    'first_name': personal_data.first_name,
                    'second_name': personal_data.second_name,
                    'last_name': personal_data.last_name,
                    'patronymic': personal_data.patronymic,
                    'birth_date': personal_data.birth_date,
                    'citizenship': personal_data.citizenship,
                } if personal_data else None,
                'documents': documents,
            }
    elif row.entity_type == ModerationQueueEntityType.complaint:
        complaint = db.execute(select(Complaint).where(Complaint.id == row.entity_id)).scalar_one_or_none()
        if complaint:
            target_preview: dict = {}
            if complaint.target_type == ComplaintTargetType.sketch:
                sketch = db.execute(select(Sketch).where(Sketch.id == complaint.target_id)).scalar_one_or_none()
                if sketch:
                    first_media = db.execute(
                        select(SketchMedia).where(SketchMedia.sketch_id == sketch.id).order_by(SketchMedia.sort_order.asc())
                    ).scalars().first()
                    target_preview = {
                        'kind': 'sketch',
                        'title': sketch.title,
                        'description': sketch.description,
                        'image_url': resolve_media_url(first_media.url) if first_media else None,
                    }
            elif complaint.target_type == ComplaintTargetType.comment:
                comment = db.execute(select(SketchComment).where(SketchComment.id == complaint.target_id)).scalar_one_or_none()
                if comment:
                    target_preview = {
                        'kind': 'comment',
                        'text': comment.body,
                        'sketch_id': str(comment.sketch_id),
                    }
            elif complaint.target_type == ComplaintTargetType.message:
                message = db.execute(select(Message).where(Message.id == complaint.target_id)).scalar_one_or_none()
                if message:
                    attachment = db.execute(
                        select(MessageAttachment).where(MessageAttachment.message_id == message.id).order_by(MessageAttachment.created_at.asc())
                    ).scalars().first()
                    target_preview = {
                        'kind': 'message',
                        'text': message.text,
                        'attachment_url': resolve_media_url(attachment.file_url) if attachment else None,
                    }

            payload = {
                'id': str(complaint.id),
                'author_id': str(complaint.author_id),
                'target_type': complaint.target_type.value,
                'target_id': str(complaint.target_id),
                'target_owner_user_id': resolve_target_owner_user_id(
                    db,
                    complaint.target_type,
                    str(complaint.target_id),
                ),
                'reason': complaint.reason,
                'details': complaint.details,
                'status': complaint.status.value,
                'created_at': complaint.created_at,
                'target_preview': target_preview,
            }
            if row.entity_type == ModerationQueueEntityType.suspicious_case:
                related = db.execute(
                    select(Complaint)
                    .where(
                        Complaint.target_type == complaint.target_type,
                        Complaint.target_id == complaint.target_id,
                    )
                    .order_by(Complaint.created_at.desc())
                    .limit(10)
                ).scalars().all()
                payload['related_complaints'] = [
                    {
                        'id': str(item.id),
                        'author_id': str(item.author_id),
                        'reason': item.reason,
                        'details': item.details,
                        'status': item.status.value,
                        'created_at': item.created_at.isoformat(),
                    }
                    for item in related
                ]
    elif row.entity_type == ModerationQueueEntityType.appeal:
        appeal = db.execute(select(Appeal).where(Appeal.id == row.entity_id)).scalar_one_or_none()
        if appeal:
            attachment_rows = db.execute(
                select(AppealAttachment)
                .where(AppealAttachment.appeal_id == appeal.id)
                .order_by(AppealAttachment.created_at.asc())
            ).scalars().all()
            payload = {
                'id': str(appeal.id),
                'appellant_user_id': str(appeal.appellant_user_id),
                'target_type': appeal.target_type.value,
                'target_id': str(appeal.target_id),
                'description': appeal.description,
                'reason_text': appeal.reason_text,
                'status': appeal.status.value,
                'created_at': appeal.created_at,
                'reviewed_at': appeal.reviewed_at.isoformat() if appeal.reviewed_at else None,
                'decision_note': appeal.decision_note,
                'attachments': [
                    {
                        'id': str(attachment.id),
                        'file_url': resolve_media_url(attachment.file_url),
                        'file_type': attachment.file_type.value,
                        'created_at': attachment.created_at.isoformat(),
                    }
                    for attachment in attachment_rows
                ],
            }

    return {
        'queue_id': str(row.id),
        'entity_type': row.entity_type.value,
        'entity_id': str(row.entity_id),
        'payload': payload,
    }


def take_queue_item(db: Session, *, queue_id: str, moderator_id: str) -> ModerationQueueItem | None:
    queue_uuid = _to_uuid(queue_id)
    moderator_uuid = _to_uuid(moderator_id)
    if not queue_uuid or not moderator_uuid:
        return None

    row = db.execute(select(ModerationQueueItem).where(ModerationQueueItem.id == queue_uuid)).scalar_one_or_none()
    if not row:
        return None

    row.assigned_moderator_id = moderator_uuid
    if row.status == ModerationQueueStatus.open:
        row.status = ModerationQueueStatus.in_progress
        if row.entity_type in {
            ModerationQueueEntityType.complaint,
            ModerationQueueEntityType.message_report,
            ModerationQueueEntityType.suspicious_case,
        }:
            complaint = db.execute(select(Complaint).where(Complaint.id == row.entity_id)).scalar_one_or_none()
            if complaint and complaint.status == ComplaintStatus.open:
                complaint.status = ComplaintStatus.in_review
        elif row.entity_type == ModerationQueueEntityType.verification:
            request = db.execute(select(MasterVerificationRequest).where(MasterVerificationRequest.id == row.entity_id)).scalar_one_or_none()
            if request and request.status == VerificationStatus.submitted:
                request.status = VerificationStatus.in_review
        elif row.entity_type == ModerationQueueEntityType.appeal:
            appeal = db.execute(select(Appeal).where(Appeal.id == row.entity_id)).scalar_one_or_none()
            if appeal and appeal.status == AppealStatus.submitted:
                appeal.status = AppealStatus.in_review
    target = _queue_target(db, row)
    if target:
        target_type, target_id = target
        db.add(
            ModerationAction(
                moderator_id=moderator_uuid,
                action_type=ModerationActionType.resolve_complaint,
                target_type=target_type,
                target_id=target_id,
                reason='taken_in_review',
                params={'queue_id': str(row.id), 'action': 'take', 'entity_type': row.entity_type.value},
            )
        )
    db.flush()
    return row


def enqueue_suspicious_case_for_complaint(db: Session, complaint_id: str) -> ModerationQueueItem | None:
    complaint_uuid = _to_uuid(complaint_id)
    if not complaint_uuid:
        return None
    complaint = db.execute(select(Complaint).where(Complaint.id == complaint_uuid)).scalar_one_or_none()
    if not complaint:
        return None

    related_count = _count(
        db,
        select(func.count()).select_from(Complaint).where(
            Complaint.target_type == complaint.target_type,
            Complaint.target_id == complaint.target_id,
            Complaint.status.in_([ComplaintStatus.open, ComplaintStatus.in_review]),
        ),
    )
    if related_count < 3:
        return None

    existing = db.execute(
        select(ModerationQueueItem)
        .join(Complaint, Complaint.id == ModerationQueueItem.entity_id)
        .where(
            ModerationQueueItem.entity_type == ModerationQueueEntityType.suspicious_case,
            ModerationQueueItem.status.in_([ModerationQueueStatus.open, ModerationQueueStatus.in_progress]),
            Complaint.target_type == complaint.target_type,
            Complaint.target_id == complaint.target_id,
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    moderator_uuid = None
    moderator_id = _first_moderator_id(db)
    if moderator_id:
        moderator_uuid = _to_uuid(moderator_id)

    row = ModerationQueueItem(
        entity_type=ModerationQueueEntityType.suspicious_case,
        entity_id=complaint_uuid,
        priority=1,
        status=ModerationQueueStatus.open,
        assigned_moderator_id=moderator_uuid,
    )
    db.add(row)
    db.flush()
    return row


def _ensure_reason(
    db: Session,
    code: str,
    title: str,
    description: str | None = None,
    applies_to: str = 'moderation_reject',
) -> ModerationReason:
    row = db.execute(select(ModerationReason).where(ModerationReason.code == code)).scalar_one_or_none()
    if row:
        return row
    row = ModerationReason(
        code=code,
        title=title,
        description=description,
        applies_to=applies_to,
        priority=2,
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def _reason_text_by_id(db: Session, reason_id: str | None, fallback: str | None) -> tuple[str, str | None]:
    if reason_id:
        reason_uuid = _to_uuid(reason_id)
        if reason_uuid:
            reason_row = db.execute(select(ModerationReason).where(ModerationReason.id == reason_uuid)).scalar_one_or_none()
            if reason_row:
                return (fallback or reason_row.description or reason_row.title or 'Moderation decision').strip(), str(reason_row.id)
    return (fallback or 'Moderation decision').strip(), None


def _consume_active_warnings(db: Session, user_id, restriction_id, resolved_at: datetime) -> None:
    rows = db.execute(
        select(UserWarning)
        .where(UserWarning.user_id == user_id, UserWarning.status == 'active')
        .order_by(UserWarning.created_at.asc())
    ).scalars().all()
    if len(rows) < 2:
        return
    for warning in rows:
        warning.status = 'consumed'
        warning.related_restriction_id = restriction_id
        warning.resolved_at = resolved_at


def _first_sketch_image(db: Session, sketch_id) -> str | None:
    raw = db.execute(
        select(SketchMedia.url)
        .where(SketchMedia.sketch_id == sketch_id)
        .order_by(SketchMedia.sort_order.asc())
        .limit(1)
    ).scalar_one_or_none()
    return resolve_media_url(raw) if raw else None


def delete_sketch_from_moderation(
    db: Session,
    *,
    sketch_id: str,
    moderator_id: str,
    reason: str | None = None,
    complaint_id: str | None = None,
) -> dict | None:
    sketch = db.execute(select(Sketch).where(Sketch.id == sketch_id)).scalar_one_or_none()
    if not sketch:
        return None

    image_url = _first_sketch_image(db, sketch_id)
    db.execute(CollectionItem.__table__.delete().where(CollectionItem.sketch_id == sketch.id))
    db.execute(SketchLike.__table__.delete().where(SketchLike.sketch_id == sketch.id))
    db.execute(SketchPin.__table__.delete().where(SketchPin.sketch_id == sketch.id))
    comment_ids = db.execute(select(SketchComment.id).where(SketchComment.sketch_id == sketch.id)).scalars().all()
    if comment_ids:
        db.execute(CommentAttachment.__table__.delete().where(CommentAttachment.comment_id.in_(comment_ids)))
        db.execute(SketchCommentLike.__table__.delete().where(SketchCommentLike.comment_id.in_(comment_ids)))
    db.execute(SketchComment.__table__.delete().where(SketchComment.sketch_id == sketch.id))
    db.execute(SketchStyle.__table__.delete().where(SketchStyle.sketch_id == sketch.id))
    db.execute(SketchTag.__table__.delete().where(SketchTag.sketch_id == sketch.id))
    db.execute(SketchMedia.__table__.delete().where(SketchMedia.sketch_id == sketch.id))
    create_notification(
        db,
        user_id=str(sketch.author_id),
        type_=NotificationType.moderation,
        title='Скетч удалён',
        body='Ваш скетч был удалён модераторами.',
        deep_link='/notifications',
        image_url=image_url,
        links=[('sketch', sketch_id)],
    )
    collection_owner_rows = db.execute(
        select(Collection.owner_id)
        .join(CollectionItem, CollectionItem.collection_id == Collection.id)
        .where(CollectionItem.sketch_id == sketch.id)
        .distinct()
    ).all()

    notified_owner_ids: set[str] = set()
    for (owner_id,) in collection_owner_rows:
        owner_id = str(owner_id)
        if owner_id == str(sketch.author_id) or owner_id in notified_owner_ids:
            continue
        notified_owner_ids.add(owner_id)
        create_notification(
            db,
            user_id=owner_id,
            type_=NotificationType.moderation,
            title='Скетч удалён из коллекции',
            body='Скетч из вашей коллекции был удалён модераторами.',
            deep_link='/collections',
            image_url=image_url,
            links=[('sketch', sketch_id)],
        )

    db.add(
        ModerationAction(
            moderator_id=moderator_id,
            action_type=ModerationActionType.remove_content,
            target_type=ComplaintTargetType.sketch,
            target_id=sketch.id,
            complaint_id=_to_uuid(complaint_id) if complaint_id else None,
            reason=reason or 'sketch removed by moderator',
            params={
                'complaint_id': complaint_id,
                'collection_owner_count': len(notified_owner_ids),
            },
        )
    )

    db.delete(sketch)
    db.flush()
    return {
        'sketch_id': str(sketch.id),
        'collection_owner_count': len(notified_owner_ids),
    }


def _queue_target(db: Session, row: ModerationQueueItem) -> tuple[ComplaintTargetType, UUID] | None:
    if row.entity_type == ModerationQueueEntityType.new_post:
        return ComplaintTargetType.sketch, row.entity_id
    if row.entity_type in {
        ModerationQueueEntityType.complaint,
        ModerationQueueEntityType.message_report,
        ModerationQueueEntityType.suspicious_case,
    }:
        complaint = db.execute(select(Complaint).where(Complaint.id == row.entity_id)).scalar_one_or_none()
        if complaint:
            return complaint.target_type, complaint.target_id
    if row.entity_type == ModerationQueueEntityType.verification:
        request = db.execute(select(MasterVerificationRequest).where(MasterVerificationRequest.id == row.entity_id)).scalar_one_or_none()
        if request:
            return ComplaintTargetType.user, request.master_id
    if row.entity_type == ModerationQueueEntityType.appeal:
        appeal = db.execute(select(Appeal).where(Appeal.id == row.entity_id)).scalar_one_or_none()
        if appeal:
            return ComplaintTargetType.user, appeal.appellant_user_id
    return None


def approve_queue_item(db: Session, *, queue_id: str, moderator_id: str, favorite: bool = False) -> ModerationQueueItem | None:
    queue_uuid = _to_uuid(queue_id)
    if not queue_uuid:
        return None

    row = db.execute(select(ModerationQueueItem).where(ModerationQueueItem.id == queue_uuid)).scalar_one_or_none()
    if not row:
        return None

    if row.entity_type == ModerationQueueEntityType.new_post:
        sketch = db.execute(select(Sketch).where(Sketch.id == row.entity_id)).scalar_one_or_none()
        if sketch:
            sketch.reviewed = True
            db.add(
                ModerationAction(
                    moderator_id=moderator_id,
                    action_type=ModerationActionType.restore_content,
                    target_type=ComplaintTargetType.sketch,
                    target_id=sketch.id,
                    reason='approved',
                    params={'queue_id': str(row.id), 'decision': 'approve'},
                )
            )
    elif row.entity_type in {
        ModerationQueueEntityType.complaint,
        ModerationQueueEntityType.message_report,
        ModerationQueueEntityType.suspicious_case,
    }:
        complaint = db.execute(select(Complaint).where(Complaint.id == row.entity_id)).scalar_one_or_none()
        if complaint:
            complaint.status = ComplaintStatus.resolved
            if row.entity_type == ModerationQueueEntityType.suspicious_case:
                related = db.execute(
                    select(Complaint).where(
                        Complaint.target_type == complaint.target_type,
                        Complaint.target_id == complaint.target_id,
                        Complaint.status.in_([ComplaintStatus.open, ComplaintStatus.in_review]),
                    )
                ).scalars().all()
                for item in related:
                    item.status = ComplaintStatus.resolved
            db.add(
                ModerationAction(
                    moderator_id=moderator_id,
                    action_type=ModerationActionType.resolve_complaint,
                    target_type=complaint.target_type,
                    target_id=complaint.target_id,
                    complaint_id=complaint.id,
                    reason='complaint approved',
                    params={'queue_id': str(row.id), 'decision': 'approve'},
                )
            )
    elif row.entity_type == ModerationQueueEntityType.verification:
        request = db.execute(select(MasterVerificationRequest).where(MasterVerificationRequest.id == row.entity_id)).scalar_one_or_none()
        if request:
            request.status = VerificationStatus.approved
            request.reviewed_at = datetime.now(timezone.utc)
            request.reviewed_by_moderator_id = moderator_id
            if favorite:
                master_profile = db.execute(select(MasterProfile).where(MasterProfile.user_id == request.master_id)).scalar_one_or_none()
                if master_profile:
                    master_profile.is_favorite = True
                    master_profile.is_verified = True
            else:
                master_profile = db.execute(select(MasterProfile).where(MasterProfile.user_id == request.master_id)).scalar_one_or_none()
                if master_profile:
                    master_profile.is_verified = True
            db.add(
                ModerationAction(
                    moderator_id=moderator_id,
                    action_type=ModerationActionType.restore_content,
                    target_type=ComplaintTargetType.user,
                    target_id=request.master_id,
                    reason='verification approved',
                    params={'queue_id': str(row.id), 'verification_request_id': str(request.id), 'favorite': favorite},
                )
            )
    elif row.entity_type == ModerationQueueEntityType.appeal:
        appeal = db.execute(select(Appeal).where(Appeal.id == row.entity_id)).scalar_one_or_none()
        if appeal:
            approve_appeal(db, appeal=appeal, moderator_id=moderator_id, note='Апелляция одобрена модератором')

    row.status = ModerationQueueStatus.done
    db.flush()
    return row


def reject_queue_item(
    db: Session,
    *,
    queue_id: str,
    moderator_id: str,
    reason: str | None,
    reason_id: str | None = None,
    block_author: bool = False,
) -> ModerationQueueItem | None:
    queue_uuid = _to_uuid(queue_id)
    if not queue_uuid:
        return None

    row = db.execute(select(ModerationQueueItem).where(ModerationQueueItem.id == queue_uuid)).scalar_one_or_none()
    if not row:
        return None

    reason_text, selected_reason_id = _reason_text_by_id(db, reason_id, reason)

    if row.entity_type == ModerationQueueEntityType.new_post:
        sketch = db.execute(select(Sketch).where(Sketch.id == row.entity_id)).scalar_one_or_none()
        if sketch:
            sketch.feed_visibility = 'private'
            sketch.reviewed = True

            db.add(
                ModerationAction(
                    moderator_id=moderator_id,
                    action_type=ModerationActionType.remove_content,
                    target_type=ComplaintTargetType.sketch,
                    target_id=sketch.id,
                    reason=reason_text,
                    params={'queue_id': str(row.id), 'decision': 'reject', 'reason_id': selected_reason_id},
                )
            )
            image_url = _first_sketch_image(db, sketch.id)

            create_notification(
                db,
                user_id=str(sketch.author_id),
                type_=NotificationType.moderation,
                title='Ваш пост удален',
                body=reason_text,
                deep_link='/notifications',
                image_url=image_url,
                links=[('sketch', str(sketch.id))],
            )

            if block_author:
                reason_row = _ensure_reason(db, 'policy_violation', 'Policy violation', reason_text)
                starts_at = datetime.now(timezone.utc)
                restriction = UserRestriction(
                    user_id=sketch.author_id,
                    imposed_by_moderator_id=moderator_id,
                    restriction_type=RestrictionType.full_block,
                    starts_at=starts_at,
                    ends_at=None,
                    is_active=True,
                    reason_id=reason_row.id,
                )
                db.add(restriction)
                db.flush()
                _consume_active_warnings(db, sketch.author_id, restriction.id, starts_at)
                db.add(
                    ModerationAction(
                        moderator_id=moderator_id,
                        action_type=ModerationActionType.block_user,
                    target_type=ComplaintTargetType.user,
                    target_id=sketch.author_id,
                    reason=reason_text,
                    params={'queue_id': str(row.id), 'decision': 'block_author', 'reason_id': selected_reason_id},
                )
            )
    elif row.entity_type in {
        ModerationQueueEntityType.complaint,
        ModerationQueueEntityType.message_report,
        ModerationQueueEntityType.suspicious_case,
    }:
        complaint = db.execute(select(Complaint).where(Complaint.id == row.entity_id)).scalar_one_or_none()
        if complaint:
            complaint.status = ComplaintStatus.rejected
            db.add(
                ModerationAction(
                    moderator_id=moderator_id,
                    action_type=ModerationActionType.resolve_complaint,
                    target_type=complaint.target_type,
                    target_id=complaint.target_id,
                    complaint_id=complaint.id,
                    reason=reason_text,
                    params={'queue_id': str(row.id), 'decision': 'reject', 'reason_id': selected_reason_id},
                )
            )
    elif row.entity_type == ModerationQueueEntityType.verification:
        request = db.execute(select(MasterVerificationRequest).where(MasterVerificationRequest.id == row.entity_id)).scalar_one_or_none()
        if request:
            request.status = VerificationStatus.rejected
            request.reviewed_at = datetime.now(timezone.utc)
            request.reviewed_by_moderator_id = moderator_id
            request.rejection_reason = reason_text
            create_notification(
                db,
                user_id=str(request.master_id),
                type_=NotificationType.moderation,
                title='Верификация отклонена',
                body=reason_text,
                deep_link='/profile/me',
                image_url=push_icon_url('verification'),
                send_push_too=True,
                in_app=True,
            )
            db.add(
                ModerationAction(
                    moderator_id=moderator_id,
                    action_type=ModerationActionType.remove_content,
                    target_type=ComplaintTargetType.user,
                    target_id=request.master_id,
                    reason=reason_text,
                    params={'queue_id': str(row.id), 'verification_request_id': str(request.id), 'decision': 'reject', 'reason_id': selected_reason_id},
                )
            )
    elif row.entity_type == ModerationQueueEntityType.appeal:
        appeal = db.execute(select(Appeal).where(Appeal.id == row.entity_id)).scalar_one_or_none()
        if appeal:
            reject_appeal(db, appeal=appeal, moderator_id=moderator_id, note=reason_text)

    row.status = ModerationQueueStatus.done
    db.flush()
    return row


def search_users_for_moderation(
    db: Session,
    *,
    q: str | None,
    role: str | None,
    is_verified: bool | None,
    limit: int,
    offset: int,
) -> list[dict]:
    stmt = select(User, Profile).outerjoin(Profile, Profile.user_id == User.id)

    if q:
        like = f'%{q.strip()}%'
        stmt = stmt.where(
            or_(
                User.email.ilike(like),
                User.phone.ilike(like),
                Profile.nickname.ilike(like),
            )
        )

    if role:
        stmt = stmt.where(User.role == role)

    if is_verified is not None:
        stmt = stmt.outerjoin(MasterProfile, MasterProfile.user_id == User.id)
        stmt = stmt.where(User.role == UserRole.master, MasterProfile.is_verified == is_verified)

    rows = db.execute(stmt.order_by(User.id.asc()).limit(limit).offset(offset)).all()

    result: list[dict] = []
    for user, profile in rows:
        verified = bool(user.is_verified)
        favorite = False
        if user.role == UserRole.master:
            master_row = db.execute(
                select(MasterProfile.is_verified, MasterProfile.is_favorite)
                .where(MasterProfile.user_id == user.id)
            ).first()
            if master_row is not None:
                verified = bool(master_row.is_verified)
                favorite = bool(master_row.is_favorite)

        result.append(
            {
                'id': str(user.id),
                'role': user.role.value,
                'email': user.email,
                'phone': user.phone,
                'is_verified': verified,
                'is_favorite': favorite,
                'nickname': profile.nickname if profile else None,
                'avatar_url': resolve_media_url(profile.avatar_url) if profile and profile.avatar_url else None,
            }
        )
    return result


def get_user_for_moderation(db: Session, *, user_id: str) -> dict | None:
    user_uuid = _to_uuid(user_id)
    if not user_uuid:
        return None

    user = db.execute(select(User).where(User.id == user_uuid)).scalar_one_or_none()
    if not user:
        return None

    profile = db.execute(select(Profile).where(Profile.user_id == user_uuid)).scalar_one_or_none()
    master_profile = db.execute(select(MasterProfile).where(MasterProfile.user_id == user_uuid)).scalar_one_or_none()

    stats = {
        'followers_count': _count(db, select(func.count()).select_from(Subscription).where(Subscription.followed_id == user_uuid)),
        'following_count': _count(db, select(func.count()).select_from(Subscription).where(Subscription.follower_id == user_uuid)),
        'sketches_count': _count(db, select(func.count()).select_from(Sketch).where(Sketch.author_id == user_uuid)),
        'collections_count': _count(db, select(func.count()).select_from(Collection).where(Collection.owner_id == user_uuid)),
        'comments_count': _count(db, select(func.count()).select_from(SketchComment).where(SketchComment.author_user_id == user_uuid)),
        'likes_given_count': _count(db, select(func.count()).select_from(SketchLike).where(SketchLike.user_id == user_uuid)),
        'chats_count': _count(db, select(func.count()).select_from(ChatParticipant).where(ChatParticipant.user_id == user_uuid)),
        'messages_count': _count(db, select(func.count()).select_from(Message).where(Message.sender_id == user_uuid)),
        'complaints_authored_count': _count(db, select(func.count()).select_from(Complaint).where(Complaint.author_id == user_uuid)),
        'complaints_against_count': _count(
            db,
            select(func.count()).select_from(Complaint).where(
                Complaint.target_type == ComplaintTargetType.user,
                Complaint.target_id == user_uuid,
            ),
        ),
        'active_restrictions_count': _count(
            db,
            select(func.count()).select_from(UserRestriction).where(
                UserRestriction.user_id == user_uuid,
                UserRestriction.is_active.is_(True),
            ),
        ),
    }

    profile_payload = None
    if profile:
        profile_payload = {
            'nickname': profile.nickname,
            'avatar_url': resolve_media_url(profile.avatar_url) if profile.avatar_url else None,
            'bio': profile.bio,
            'home_location_id': str(profile.home_location_id) if profile.home_location_id else None,
            'default_currency': profile.default_currency,
            'created_at': profile.created_at,
            'updated_at': profile.updated_at,
        }

    master_payload = None
    if master_profile:
        master_payload = {
            'experience_years': master_profile.experience_years,
            'price_min': master_profile.price_min,
            'price_max': master_profile.price_max,
            'description': master_profile.description,
            'is_verified': bool(master_profile.is_verified),
            'is_favorite': bool(master_profile.is_favorite),
            'rating_avg': float(master_profile.rating_avg or 0),
            'completed_sessions_count': int(master_profile.completed_sessions_count or 0),
        }

    return {
        'id': str(user.id),
        'role': user.role.value,
        'email': user.email,
        'phone': user.phone,
        'is_verified': bool(user.is_verified),
        'is_favorite': bool(master_profile.is_favorite) if master_profile else False,
        'profile': profile_payload,
        'master_profile': master_payload,
        'stats': stats,
    }


def _apply_range(stmt, column, date_from: datetime | None, date_to: datetime | None):
    if date_from is not None:
        stmt = stmt.where(column >= date_from)
    if date_to is not None:
        stmt = stmt.where(column <= date_to)
    return stmt


def _avg(db: Session, stmt) -> float:
    value = db.execute(stmt).scalar_one_or_none()
    if value is None:
        return 0.0
    return float(value)




def _activity_counts_by_user(db: Session, *, date_from: datetime | None = None, date_to: datetime | None = None) -> list[dict]:
    messages_stmt = _apply_range(
        select(Message.sender_id, func.count())
        .where(Message.sender_id.is_not(None))
        .group_by(Message.sender_id),
        Message.created_at,
        date_from,
        date_to,
    )
    comments_stmt = _apply_range(
        select(SketchComment.author_user_id, func.count())
        .where(SketchComment.is_deleted.is_(False))
        .group_by(SketchComment.author_user_id),
        SketchComment.created_at,
        date_from,
        date_to,
    )
    likes_stmt = _apply_range(
        select(SketchLike.user_id, func.count())
        .group_by(SketchLike.user_id),
        SketchLike.created_at,
        date_from,
        date_to,
    )
    complaints_stmt = _apply_range(
        select(Complaint.author_id, func.count())
        .group_by(Complaint.author_id),
        Complaint.created_at,
        date_from,
        date_to,
    )

    messages = db.execute(messages_stmt).all()
    comments = db.execute(comments_stmt).all()
    likes = db.execute(likes_stmt).all()
    complaints = db.execute(complaints_stmt).all()

    def _collect(rows, key):
        out = {}
        for user_id, cnt in rows:
            if user_id is None:
                continue
            out[str(user_id)] = int(cnt)
        return out

    messages_map = _collect(messages, 'messages')
    comments_map = _collect(comments, 'comments')
    likes_map = _collect(likes, 'likes')
    complaints_map = _collect(complaints, 'complaints')

    user_ids = set(messages_map) | set(comments_map) | set(likes_map) | set(complaints_map)
    result = []
    for user_id in user_ids:
        nickname = db.execute(select(Profile.nickname).where(Profile.user_id == user_id)).scalar_one_or_none()
        role = db.execute(select(User.role).where(User.id == user_id)).scalar_one_or_none()
        total = messages_map.get(user_id, 0) + comments_map.get(user_id, 0) + likes_map.get(user_id, 0) + complaints_map.get(user_id, 0)
        result.append({
            'user_id': user_id,
            'nickname': nickname,
            'role': role.value if role else 'unknown',
            'messages_sent': messages_map.get(user_id, 0),
            'comments_created': comments_map.get(user_id, 0),
            'likes_given': likes_map.get(user_id, 0),
            'complaints_created': complaints_map.get(user_id, 0),
            'total_activity': total,
        })
    result.sort(key=lambda item: (-item['total_activity'], item['nickname'] or item['user_id']))
    return result[:10]

def get_moderation_dashboard_stats(
    db: Session,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict:
    queue_base = _apply_range(select(func.count()).select_from(ModerationQueueItem), ModerationQueueItem.created_at, date_from, date_to)
    complaints_base = _apply_range(select(func.count()).select_from(Complaint), Complaint.created_at, date_from, date_to)

    queue_open = _count(db, queue_base.where(ModerationQueueItem.status == ModerationQueueStatus.open))
    queue_in_progress = _count(db, queue_base.where(ModerationQueueItem.status == ModerationQueueStatus.in_progress))
    queue_done = _count(db, queue_base.where(ModerationQueueItem.status == ModerationQueueStatus.done))

    queue_complaints_open = _count(
        db,
        queue_base.where(
            ModerationQueueItem.status.in_([ModerationQueueStatus.open, ModerationQueueStatus.in_progress]),
            ModerationQueueItem.entity_type == ModerationQueueEntityType.complaint,
        ),
    )
    queue_new_posts_open = _count(
        db,
        queue_base.where(
            ModerationQueueItem.status.in_([ModerationQueueStatus.open, ModerationQueueStatus.in_progress]),
            ModerationQueueItem.entity_type == ModerationQueueEntityType.new_post,
        ),
    )

    complaints_open = _count(db, complaints_base.where(Complaint.status == ComplaintStatus.open))
    complaints_in_review = _count(db, complaints_base.where(Complaint.status == ComplaintStatus.in_review))
    complaints_resolved = _count(db, complaints_base.where(Complaint.status == ComplaintStatus.resolved))
    complaints_rejected = _count(db, complaints_base.where(Complaint.status == ComplaintStatus.rejected))

    restrictions_stmt = _apply_range(
        select(func.count()).select_from(UserRestriction).where(UserRestriction.is_active.is_(True)),
        UserRestriction.created_at,
        date_from,
        date_to,
    )
    actions_stmt = _apply_range(
        select(func.count()).select_from(ModerationAction),
        ModerationAction.occurred_at,
        date_from,
        date_to,
    )

    posts_created = _count(
        db,
        _apply_range(select(func.count()).select_from(Sketch), Sketch.created_at, date_from, date_to),
    )
    profiles_created = _count(
        db,
        _apply_range(select(func.count()).select_from(Profile), Profile.created_at, date_from, date_to),
    )
    chats_created = _count(
        db,
        _apply_range(select(func.count()).select_from(Chat), Chat.created_at, date_from, date_to),
    )
    messages_sent = _count(
        db,
        _apply_range(select(func.count()).select_from(Message), Message.created_at, date_from, date_to),
    )
    collections_created = _count(
        db,
        _apply_range(select(func.count()).select_from(Collection), Collection.created_at, date_from, date_to),
    )
    comments_created = _count(
        db,
        _apply_range(select(func.count()).select_from(SketchComment), SketchComment.created_at, date_from, date_to),
    )
    reviews_created = _count(
        db,
        _apply_range(select(func.count()).select_from(InkmatchReview), InkmatchReview.created_at, date_from, date_to),
    )

    avg_queue_priority = _avg(
        db,
        _apply_range(
            select(func.avg(ModerationQueueItem.priority)).select_from(ModerationQueueItem),
            ModerationQueueItem.created_at,
            date_from,
            date_to,
        ),
    )

    resolved_queue_rows = db.execute(
        _apply_range(
            select(ModerationQueueItem),
            ModerationQueueItem.created_at,
            date_from,
            date_to,
        ).where(ModerationQueueItem.status == ModerationQueueStatus.done)
    ).scalars().all()
    resolution_minutes: list[float] = []
    for queue_row in resolved_queue_rows:
        first_action_at = db.execute(
            select(func.min(ModerationAction.occurred_at)).where(
                ModerationAction.params['queue_id'].astext == str(queue_row.id)
            )
        ).scalar_one_or_none()
        if first_action_at:
            resolution_minutes.append((first_action_at - queue_row.created_at).total_seconds() / 60)
    avg_resolution_minutes = sum(resolution_minutes) / len(resolution_minutes) if resolution_minutes else 0.0

    top_active_users = _activity_counts_by_user(db, date_from=date_from, date_to=date_to)

    return {
        'queue_open': queue_open,
        'queue_in_progress': queue_in_progress,
        'queue_done': queue_done,
        'queue_complaints_open': queue_complaints_open,
        'queue_new_posts_open': queue_new_posts_open,
        'complaints_open': complaints_open,
        'complaints_in_review': complaints_in_review,
        'complaints_resolved': complaints_resolved,
        'complaints_rejected': complaints_rejected,
        'active_restrictions': _count(db, restrictions_stmt),
        'actions_total': _count(db, actions_stmt),
        'posts_created': posts_created,
        'users_registered': profiles_created,
        'chats_created': chats_created,
        'messages_sent': messages_sent,
        'collections_created': collections_created,
        'comments_created': comments_created,
        'reviews_created': reviews_created,
        'avg_queue_priority': round(avg_queue_priority, 2),
        'avg_resolution_minutes': round(avg_resolution_minutes, 2),
        'top_active_users': top_active_users,
    }


def get_moderator_productivity(
    db: Session,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    overdue_minutes: int = 24 * 60,
) -> list[dict]:
    moderators = db.execute(
        select(User.id, Profile.nickname)
        .outerjoin(Profile, Profile.user_id == User.id)
        .where(User.role == UserRole.moderator)
        .order_by(Profile.nickname.asc(), User.id.asc())
    ).all()
    rows = {
        str(user_id): {
            'moderator_id': str(user_id),
            'nickname': nickname,
            'taken_count': 0,
            'resolved_count': 0,
            'approved_count': 0,
            'rejected_count': 0,
            'avg_resolution_minutes': 0.0,
            'overdue_count': 0,
            '_resolution_minutes': [],
        }
        for user_id, nickname in moderators
    }

    actions = db.execute(
        _apply_range(
            select(ModerationAction),
            ModerationAction.occurred_at,
            date_from,
            date_to,
        )
    ).scalars().all()

    decision_actions_by_queue: dict[str, list[ModerationAction]] = {}
    for action in actions:
        moderator_id = str(action.moderator_id)
        rows.setdefault(
            moderator_id,
            {
                'moderator_id': moderator_id,
                'nickname': None,
                'taken_count': 0,
                'resolved_count': 0,
                'approved_count': 0,
                'rejected_count': 0,
                'avg_resolution_minutes': 0.0,
                'overdue_count': 0,
                '_resolution_minutes': [],
            },
        )
        params = action.params or {}
        if params.get('action') == 'take':
            rows[moderator_id]['taken_count'] += 1
        decision = params.get('decision')
        if decision in {'approve', 'reject'}:
            rows[moderator_id]['resolved_count'] += 1
            if decision == 'approve':
                rows[moderator_id]['approved_count'] += 1
            else:
                rows[moderator_id]['rejected_count'] += 1
            queue_id = params.get('queue_id')
            if queue_id:
                decision_actions_by_queue.setdefault(str(queue_id), []).append(action)

    done_queue_rows = db.execute(
        _apply_range(
            select(ModerationQueueItem),
            ModerationQueueItem.created_at,
            date_from,
            date_to,
        ).where(ModerationQueueItem.status == ModerationQueueStatus.done)
    ).scalars().all()

    for queue_row in done_queue_rows:
        decision_actions = decision_actions_by_queue.get(str(queue_row.id), [])
        if not decision_actions:
            continue
        first_action = min(decision_actions, key=lambda item: item.occurred_at)
        minutes = (first_action.occurred_at - queue_row.created_at).total_seconds() / 60
        moderator_id = str(first_action.moderator_id)
        rows[moderator_id]['_resolution_minutes'].append(minutes)
        if minutes > overdue_minutes:
            rows[moderator_id]['overdue_count'] += 1

    result = []
    for row in rows.values():
        values = row.pop('_resolution_minutes')
        row['avg_resolution_minutes'] = round(sum(values) / len(values), 2) if values else 0.0
        result.append(row)
    result.sort(key=lambda item: (-item['resolved_count'], -item['taken_count'], item['nickname'] or ''))
    return result


def moderation_stats_rows(
    db: Session,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[tuple[str, str]]:
    stats = get_moderation_dashboard_stats(db, date_from=date_from, date_to=date_to)
    period_from = date_from.isoformat() if date_from else '-'
    period_to = date_to.isoformat() if date_to else '-'
    rows = [
        ('period_from', period_from),
        ('period_to', period_to),
    ]
    for key, value in stats.items():
        if key == 'top_active_users':
            rows.append((key, json.dumps(value, ensure_ascii=False)))
        else:
            rows.append((key, str(value)))
    return rows


def moderation_stats_trends(
    db: Session,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[dict]:
    message_stmt = _apply_range(select(Message), Message.created_at, date_from, date_to)
    comment_stmt = _apply_range(select(SketchComment), SketchComment.created_at, date_from, date_to)
    complaint_stmt = _apply_range(select(Complaint), Complaint.created_at, date_from, date_to)

    buckets: dict[str, dict[str, int]] = {}

    for row in db.execute(message_stmt).scalars().all():
        period = row.created_at.strftime('%Y-%m-%d')
        buckets.setdefault(period, {'messages_sent': 0, 'comments_created': 0, 'complaints_created': 0})
        buckets[period]['messages_sent'] += 1

    for row in db.execute(comment_stmt).scalars().all():
        period = row.created_at.strftime('%Y-%m-%d')
        buckets.setdefault(period, {'messages_sent': 0, 'comments_created': 0, 'complaints_created': 0})
        buckets[period]['comments_created'] += 1

    for row in db.execute(complaint_stmt).scalars().all():
        period = row.created_at.strftime('%Y-%m-%d')
        buckets.setdefault(period, {'messages_sent': 0, 'comments_created': 0, 'complaints_created': 0})
        buckets[period]['complaints_created'] += 1

    result = []
    for period in sorted(buckets.keys()):
        item = buckets[period]
        result.append({
            'period': period,
            'messages_sent': item['messages_sent'],
            'comments_created': item['comments_created'],
            'complaints_created': item['complaints_created'],
        })
    return result
