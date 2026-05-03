import csv
from datetime import datetime, timezone
from io import BytesIO, StringIO

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.enums import ModerationQueueEntityType, ModerationQueueStatus, RestrictionType, UserRole
from app.models.enums import ComplaintTargetType, ModerationActionType, NotificationType
from app.models.moderation import ModerationAction, ModerationReason, UserWarning
from sqlalchemy import select, func
from app.schemas.moderation import (
    ModerationDashboardStatsOut,
    ModerationStatsExtendedOut,
    ModerationUserListItemOut,
    ModerationDecisionIn,
    ModerationDecisionOut,
    ModerationQueueEntityOut,
    ModerationQueueItemOut,
    ModerationQueueTakeOut,
    ModerationUserOut,
    UserRestrictionApplyIn,
    UserRestrictionDeactivateIn,
    UserRestrictionOut,
    ModerationReasonIn,
    ModerationReasonOut,
    UserWarnIn,
    UserWarnOut,
    UserWarningOut,
)
from app.services.moderation_service import (
    approve_queue_item,
    get_moderation_dashboard_stats,
    get_moderator_productivity,
    get_queue_item_entity,
    get_user_for_moderation,
    moderation_stats_trends,
    search_users_for_moderation,
    list_queue_items,
    moderation_stats_rows,
    reject_queue_item,
    take_queue_item,
)
from app.services.restriction_service import (
    apply_user_restriction,
    deactivate_user_restriction,
    list_user_restrictions,
    serialize_restriction,
)
from app.services.notification_service import create_notification
from app.services.complaint_service import COMPLAINT_REASON_CATALOG
from app.services.verification_service import send_weekly_unverified_master_reminders

router = APIRouter()


def _require_moderator(user):
    if user.role != UserRole.moderator:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Moderator role required')


def _parse_datetime(raw: str | None, field_name: str) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Invalid {field_name}. Use ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS',
        ) from exc


@router.get('/queue', response_model=list[ModerationQueueItemOut])
def moderation_queue(
    status_filter: str | None = Query(default='open', alias='status'),
    entity_type: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_moderator(current_user)

    parsed_status = None
    if status_filter:
        try:
            parsed_status = ModerationQueueStatus(status_filter)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid status') from exc

    items = list_queue_items(
        db,
        moderator_id=str(current_user.id),
        status_filter=parsed_status,
        limit=limit,
        offset=offset,
    )

    if entity_type:
        try:
            parsed_entity_type = ModerationQueueEntityType(entity_type)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid entity_type') from exc
        items = [item for item in items if item.get('entity_type') == parsed_entity_type.value]

    return items


@router.get('/queue/{queue_id}', response_model=ModerationQueueEntityOut)
def moderation_queue_entity(
    queue_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_moderator(current_user)
    payload = get_queue_item_entity(db, queue_id=queue_id)
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Queue item not found')
    return payload


@router.post('/queue/{queue_id}/take', response_model=ModerationQueueTakeOut)
def take_item(queue_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    _require_moderator(current_user)
    row = take_queue_item(db, queue_id=queue_id, moderator_id=str(current_user.id))
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Queue item not found')

    db.commit()
    return {
        'id': str(row.id),
        'status': row.status.value,
        'assigned_moderator_id': str(row.assigned_moderator_id),
    }


@router.post('/queue/{queue_id}/approve', response_model=ModerationDecisionOut)
def approve_item(
    queue_id: str,
    payload: ModerationDecisionIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_moderator(current_user)
    row = approve_queue_item(
        db,
        queue_id=queue_id,
        moderator_id=str(current_user.id),
        favorite=payload.favorite,
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Queue item not found')

    db.commit()
    return {'id': str(row.id), 'status': row.status.value, 'action': 'approve'}


@router.post('/queue/{queue_id}/reject', response_model=ModerationDecisionOut)
def reject_item(
    queue_id: str,
    payload: ModerationDecisionIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_moderator(current_user)
    row = reject_queue_item(
        db,
        queue_id=queue_id,
        moderator_id=str(current_user.id),
        reason=payload.reason,
        reason_id=payload.reason_id,
        block_author=payload.block_author,
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Queue item not found')

    db.commit()
    return {'id': str(row.id), 'status': row.status.value, 'action': 'reject'}


@router.post('/verification/reminders/send-weekly')
def send_verification_reminders(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    _require_moderator(current_user)
    count = send_weekly_unverified_master_reminders(db)
    return {'sent': count}


@router.get('/users', response_model=list[ModerationUserListItemOut])
def moderation_users_list(
    q: str | None = Query(default=None),
    role: str | None = Query(default=None),
    is_verified: bool | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_moderator(current_user)
    return search_users_for_moderation(
        db,
        q=q,
        role=role,
        is_verified=is_verified,
        limit=limit,
        offset=offset,
    )


@router.get('/users/{user_id}', response_model=ModerationUserOut)
def moderation_user_details(
    user_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_moderator(current_user)
    payload = get_user_for_moderation(db, user_id=user_id)
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    return payload


def _reason_out(row: ModerationReason) -> dict:
    return {
        'id': str(row.id),
        'code': row.code,
        'title': row.title,
        'description': row.description,
        'applies_to': row.applies_to,
        'priority': int(row.priority),
        'is_active': bool(row.is_active),
    }


def _warning_out(db: Session, row: UserWarning) -> dict:
    reason = None
    if row.reason_id:
        reason = db.execute(select(ModerationReason).where(ModerationReason.id == row.reason_id)).scalar_one_or_none()
    return {
        'id': str(row.id),
        'user_id': str(row.user_id),
        'issued_by_moderator_id': str(row.issued_by_moderator_id),
        'reason_id': str(row.reason_id) if row.reason_id else None,
        'reason_title': reason.title if reason else None,
        'reason_text': row.reason_text,
        'status': row.status,
        'related_restriction_id': str(row.related_restriction_id) if row.related_restriction_id else None,
        'created_at': row.created_at,
        'resolved_at': row.resolved_at,
    }


def _ensure_default_reasons(db: Session) -> None:
    existing_count = db.execute(select(func.count()).select_from(ModerationReason)).scalar_one() or 0
    if existing_count:
        return

    priority = 1
    for category in COMPLAINT_REASON_CATALOG:
        for reason in category['reasons']:
            db.add(
                ModerationReason(
                    code=f"complaint_{reason['code']}",
                    title=reason['title'],
                    description=reason.get('description'),
                    applies_to='complaint',
                    priority=priority,
                    is_active=True,
                )
            )
            priority = min(priority + 1, 10)

    for code, title, description, applies_to in [
        ('warning_policy', 'Предупреждение', 'Нарушение правил без немедленной блокировки.', 'warning'),
        ('temporary_restriction', 'Временное ограничение', 'Повторное или среднее по тяжести нарушение.', 'restriction'),
        ('permanent_block', 'Блокировка', 'Грубое или систематическое нарушение.', 'restriction'),
    ]:
        db.add(ModerationReason(code=code, title=title, description=description, applies_to=applies_to, priority=2, is_active=True))
    db.commit()


@router.get('/reasons', response_model=list[ModerationReasonOut])
def moderation_reasons(
    active_only: bool = Query(default=True),
    applies_to: str | None = Query(default=None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_moderator(current_user)
    _ensure_default_reasons(db)
    stmt = select(ModerationReason).order_by(ModerationReason.priority.asc(), ModerationReason.title.asc())
    if active_only:
        stmt = stmt.where(ModerationReason.is_active.is_(True))
    if applies_to:
        stmt = stmt.where(ModerationReason.applies_to.in_([applies_to, 'general']))
    return [_reason_out(row) for row in db.execute(stmt).scalars().all()]


@router.post('/reasons', response_model=ModerationReasonOut, status_code=status.HTTP_201_CREATED)
def create_moderation_reason(
    payload: ModerationReasonIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_moderator(current_user)
    row = ModerationReason(
        code=payload.code.strip(),
        title=payload.title.strip(),
        description=(payload.description or '').strip() or None,
        applies_to=payload.applies_to.strip(),
        priority=payload.priority,
        is_active=payload.is_active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _reason_out(row)


@router.patch('/reasons/{reason_id}', response_model=ModerationReasonOut)
def update_moderation_reason(
    reason_id: str,
    payload: ModerationReasonIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_moderator(current_user)
    row = db.execute(select(ModerationReason).where(ModerationReason.id == reason_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Reason not found')
    row.code = payload.code.strip()
    row.title = payload.title.strip()
    row.description = (payload.description or '').strip() or None
    row.applies_to = payload.applies_to.strip()
    row.priority = payload.priority
    row.is_active = payload.is_active
    db.commit()
    db.refresh(row)
    return _reason_out(row)


@router.post('/users/{user_id}/warn', response_model=UserWarnOut)
def moderation_warn_user(
    user_id: str,
    payload: UserWarnIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_moderator(current_user)
    if not get_user_for_moderation(db, user_id=user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    warnings_count = int(db.execute(
        select(func.count()).select_from(UserWarning).where(
            UserWarning.user_id == user_id,
            UserWarning.status == 'active',
        )
    ).scalar_one() or 0)
    if warnings_count >= 2:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='У пользователя уже 2 предупреждения. Нужно применить ограничение.',
        )
    reason_row = None
    if payload.reason_id:
        reason_row = db.execute(select(ModerationReason).where(ModerationReason.id == payload.reason_id)).scalar_one_or_none()
    reason_text = (payload.reason or '').strip() or (reason_row.description if reason_row else None) or (reason_row.title if reason_row else None) or 'Предупреждение модератора'
    warning = UserWarning(
        user_id=user_id,
        issued_by_moderator_id=current_user.id,
        reason_id=reason_row.id if reason_row else None,
        reason_text=reason_text,
        status='active',
    )
    db.add(warning)
    db.flush()
    db.add(
        ModerationAction(
            moderator_id=current_user.id,
            action_type=ModerationActionType.warn,
            target_type=ComplaintTargetType.user,
            target_id=user_id,
            reason=reason_text,
            params={'reason_id': str(reason_row.id) if reason_row else None, 'warning_id': str(warning.id)},
        )
    )
    create_notification(
        db,
        user_id=user_id,
        type_=NotificationType.moderation,
        title='Предупреждение модератора',
        body=reason_text,
        deep_link='/account/restrictions',
        links=[('user', user_id), ('warning', str(warning.id))],
    )
    db.commit()
    return {'user_id': user_id, 'warnings_count': warnings_count + 1, 'requires_restriction': warnings_count + 1 >= 2}


@router.get('/users/{user_id}/warnings', response_model=list[UserWarningOut])
def moderation_user_warnings(
    user_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_moderator(current_user)
    if not get_user_for_moderation(db, user_id=user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    rows = db.execute(
        select(UserWarning)
        .where(UserWarning.user_id == user_id)
        .order_by(UserWarning.created_at.desc())
    ).scalars().all()
    return [_warning_out(db, row) for row in rows]


@router.get('/users/{user_id}/restrictions', response_model=list[UserRestrictionOut])
def moderation_user_restrictions(
    user_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_moderator(current_user)
    payload = get_user_for_moderation(db, user_id=user_id)
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    return list_user_restrictions(db, user_id)


@router.post('/users/{user_id}/restrictions', response_model=UserRestrictionOut, status_code=status.HTTP_201_CREATED)
def moderation_apply_user_restriction(
    user_id: str,
    payload: UserRestrictionApplyIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_moderator(current_user)
    if not get_user_for_moderation(db, user_id=user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    try:
        restriction_type = RestrictionType(payload.restriction_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid restriction_type') from exc

    row = apply_user_restriction(
        db,
        user_id=user_id,
        moderator_id=str(current_user.id),
        restriction_type=restriction_type,
        reason=payload.reason,
        reason_id=payload.reason_id,
        duration_hours=payload.duration_hours,
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid user id')
    db.commit()
    db.refresh(row)
    return serialize_restriction(db, row)


@router.post('/restrictions/{restriction_id}/deactivate', response_model=UserRestrictionOut)
def moderation_deactivate_user_restriction(
    restriction_id: str,
    payload: UserRestrictionDeactivateIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_moderator(current_user)
    row = deactivate_user_restriction(
        db,
        restriction_id=restriction_id,
        moderator_id=str(current_user.id),
        reason=payload.reason,
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Restriction not found')
    db.commit()
    db.refresh(row)
    return serialize_restriction(db, row)


@router.get('/stats', response_model=ModerationStatsExtendedOut)
def moderation_stats(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_moderator(current_user)
    parsed_from = _parse_datetime(date_from, 'date_from')
    parsed_to = _parse_datetime(date_to, 'date_to')
    base = get_moderation_dashboard_stats(db, date_from=parsed_from, date_to=parsed_to)
    return {
        **base,
        'trends': moderation_stats_trends(db, date_from=parsed_from, date_to=parsed_to),
        'moderator_productivity': get_moderator_productivity(db, date_from=parsed_from, date_to=parsed_to),
    }


@router.get('/stats/export.csv')
def moderation_stats_export_csv(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_moderator(current_user)
    parsed_from = _parse_datetime(date_from, 'date_from')
    parsed_to = _parse_datetime(date_to, 'date_to')

    rows = moderation_stats_rows(db, date_from=parsed_from, date_to=parsed_to)
    stream = StringIO()
    writer = csv.writer(stream)
    writer.writerow(['metric', 'value'])
    for key, value in rows:
        writer.writerow([key, value])

    return Response(
        content=stream.getvalue().encode('utf-8'),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=moderation_stats.csv'},
    )


@router.get('/stats/export.xlsx')
def moderation_stats_export_xlsx(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_moderator(current_user)
    parsed_from = _parse_datetime(date_from, 'date_from')
    parsed_to = _parse_datetime(date_to, 'date_to')

    rows = moderation_stats_rows(db, date_from=parsed_from, date_to=parsed_to)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'ModerationStats'
    sheet.append(['metric', 'value'])
    for key, value in rows:
        sheet.append([key, value])

    data = BytesIO()
    workbook.save(data)
    data.seek(0)

    return Response(
        content=data.getvalue(),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename=moderation_stats.xlsx'},
    )
