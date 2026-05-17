from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ComplaintTargetType, ModerationActionType, NotificationType, RestrictionType
from app.models.moderation import ModerationAction, ModerationReason, UserWarning
from app.models.user_extras import UserRestriction
from app.services.notification_service import create_notification, push_icon_url


RESTRICTION_LABELS = {
    RestrictionType.full_block: 'Полная блокировка',
    RestrictionType.chat_only_read: 'Чат только для чтения',
    RestrictionType.posting_disabled: 'Запрет публикаций',
    RestrictionType.commenting_disabled: 'Запрет комментариев',
    RestrictionType.inkmatch_disabled: 'Запрет InkMatch',
    RestrictionType.profile_hidden: 'Профиль скрыт',
}


def _to_uuid(raw: str) -> UUID | None:
    try:
        return UUID(str(raw))
    except (TypeError, ValueError):
        return None


def restriction_label(restriction_type: RestrictionType) -> str:
    return RESTRICTION_LABELS.get(restriction_type, restriction_type.value)


def _ensure_reason(db: Session, reason_text: str, reason_id: str | None = None) -> ModerationReason | None:
    if reason_id:
        reason_uuid = _to_uuid(reason_id)
        if reason_uuid:
            row = db.execute(select(ModerationReason).where(ModerationReason.id == reason_uuid)).scalar_one_or_none()
            if row:
                return row
    code = 'manual_user_restriction'
    row = db.execute(select(ModerationReason).where(ModerationReason.code == code)).scalar_one_or_none()
    if row:
        row.description = reason_text
        return row
    row = ModerationReason(
        code=code,
        title='Ручное ограничение пользователя',
        description=reason_text,
        applies_to='restriction',
        priority=3,
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def deactivate_expired_restrictions(db: Session, user_id: str | None = None) -> None:
    now = datetime.now(timezone.utc)
    stmt = select(UserRestriction).where(
        UserRestriction.is_active.is_(True),
        UserRestriction.ends_at.is_not(None),
        UserRestriction.ends_at <= now,
    )
    user_uuid = _to_uuid(user_id) if user_id else None
    if user_uuid:
        stmt = stmt.where(UserRestriction.user_id == user_uuid)
    rows = db.execute(stmt).scalars().all()
    for row in rows:
        row.is_active = False
    if rows:
        db.flush()


def serialize_restriction(db: Session, row: UserRestriction) -> dict:
    reason = db.execute(select(ModerationReason).where(ModerationReason.id == row.reason_id)).scalar_one_or_none()
    return {
        'id': str(row.id),
        'user_id': str(row.user_id),
        'imposed_by_moderator_id': str(row.imposed_by_moderator_id),
        'restriction_type': row.restriction_type.value,
        'starts_at': row.starts_at,
        'ends_at': row.ends_at,
        'is_active': bool(row.is_active),
        'reason_id': str(row.reason_id),
        'reason_title': reason.title if reason else None,
        'reason_description': reason.description if reason else None,
        'created_at': row.created_at,
    }


def list_user_restrictions(db: Session, user_id: str, *, only_active: bool = False) -> list[dict]:
    user_uuid = _to_uuid(user_id)
    if not user_uuid:
        return []
    deactivate_expired_restrictions(db, user_id)
    stmt = select(UserRestriction).where(UserRestriction.user_id == user_uuid)
    if only_active:
        stmt = stmt.where(UserRestriction.is_active.is_(True))
    rows = db.execute(stmt.order_by(UserRestriction.created_at.desc())).scalars().all()
    return [serialize_restriction(db, row) for row in rows]


def get_active_restriction(db: Session, user_id: str, types: set[RestrictionType]) -> UserRestriction | None:
    user_uuid = _to_uuid(user_id)
    if not user_uuid:
        return None
    deactivate_expired_restrictions(db, user_id)
    return db.execute(
        select(UserRestriction)
        .where(
            UserRestriction.user_id == user_uuid,
            UserRestriction.is_active.is_(True),
            UserRestriction.restriction_type.in_([RestrictionType.full_block, *types]),
        )
        .order_by(UserRestriction.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def enforce_not_restricted(db: Session, user_id: str, *types: RestrictionType) -> None:
    restriction = get_active_restriction(db, user_id, set(types))
    if not restriction:
        return
    label = restriction_label(restriction.restriction_type)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f'Действие недоступно: {label}',
    )


def apply_user_restriction(
    db: Session,
    *,
    user_id: str,
    moderator_id: str,
    restriction_type: RestrictionType,
    reason: str | None,
    reason_id: str | None = None,
    duration_hours: int | None = None,
) -> UserRestriction | None:
    user_uuid = _to_uuid(user_id)
    moderator_uuid = _to_uuid(moderator_id)
    if not user_uuid or not moderator_uuid:
        return None

    reason_text = (reason or '').strip()
    reason_row = _ensure_reason(db, reason_text or 'Ограничение пользователя', reason_id)
    if not reason_row:
        return None
    if not reason_text:
        reason_text = reason_row.description or reason_row.title
    starts_at = datetime.now(timezone.utc)
    ends_at = starts_at + timedelta(hours=duration_hours) if duration_hours else None
    row = UserRestriction(
        user_id=user_uuid,
        imposed_by_moderator_id=moderator_uuid,
        restriction_type=restriction_type,
        starts_at=starts_at,
        ends_at=ends_at,
        is_active=True,
        reason_id=reason_row.id,
    )
    db.add(row)
    db.flush()

    active_warnings = db.execute(
        select(UserWarning)
        .where(UserWarning.user_id == user_uuid, UserWarning.status == 'active')
        .order_by(UserWarning.created_at.asc())
    ).scalars().all()
    if len(active_warnings) >= 2:
        for warning in active_warnings:
            warning.status = 'consumed'
            warning.related_restriction_id = row.id
            warning.resolved_at = starts_at

    action_type = (
        ModerationActionType.block_user
        if restriction_type == RestrictionType.full_block
        else ModerationActionType.apply_restriction
    )
    db.add(
        ModerationAction(
            moderator_id=moderator_uuid,
            action_type=action_type,
            target_type=ComplaintTargetType.user,
            target_id=user_uuid,
            reason=reason_text,
            params={
                'restriction_id': str(row.id),
                'restriction_type': restriction_type.value,
                'duration_hours': duration_hours,
                'ends_at': ends_at.isoformat() if ends_at else None,
                'action': 'apply',
            },
        )
    )

    label = restriction_label(restriction_type)
    suffix = f' Ограничение действует до {ends_at.strftime("%d.%m.%Y %H:%M")}.' if ends_at else ''
    create_notification(
        db,
        user_id=str(user_uuid),
        type_=NotificationType.moderation,
        title='Ограничение аккаунта InkMatch',
        body=f'{label}. Причина: {reason_text}.{suffix}',
        deep_link='/account/restrictions',
        image_url=push_icon_url('restriction'),
        links=[('user_restriction', str(row.id))],
        send_push_too=True,
        in_app=True,
    )
    return row


def deactivate_user_restriction(
    db: Session,
    *,
    restriction_id: str,
    moderator_id: str,
    reason: str | None = None,
) -> UserRestriction | None:
    restriction_uuid = _to_uuid(restriction_id)
    moderator_uuid = _to_uuid(moderator_id)
    if not restriction_uuid or not moderator_uuid:
        return None
    row = db.execute(select(UserRestriction).where(UserRestriction.id == restriction_uuid)).scalar_one_or_none()
    if not row:
        return None
    row.is_active = False
    reason_text = (reason or 'Ограничение снято модератором').strip()
    db.add(
        ModerationAction(
            moderator_id=moderator_uuid,
            action_type=ModerationActionType.apply_restriction,
            target_type=ComplaintTargetType.user,
            target_id=row.user_id,
            reason=reason_text,
            params={
                'restriction_id': str(row.id),
                'restriction_type': row.restriction_type.value,
                'action': 'deactivate',
            },
        )
    )
    create_notification(
        db,
        user_id=str(row.user_id),
        type_=NotificationType.moderation,
        title='Ограничение аккаунта снято',
        body=reason_text,
        deep_link='/account/restrictions',
        image_url=push_icon_url('restriction'),
        links=[('user_restriction', str(row.id))],
        send_push_too=True,
        in_app=True,
    )
    db.flush()
    return row
