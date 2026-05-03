from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.messaging import Notification, NotificationLink
from app.schemas.engagement import NotificationLinkIn, NotificationLinkOut
from app.services.notification_service import deactivate_push_token, register_push_token
from app.schemas.notification import NotificationOut, PushTokenIn

router = APIRouter()


@router.get('', response_model=list[NotificationOut])
def list_notifications(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()

    return [
        {
            'id': str(row.id),
            'type': row.type.value,
            'title': row.title,
            'body': row.body,
            'is_read': bool(row.is_read),
            'image_url': row.image_url,
            'deep_link': row.deep_link,
            'created_at': row.created_at.astimezone(timezone.utc).isoformat(),
        }
        for row in rows
    ]


@router.get('/unread-count')
def unread_count(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    value = db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
    ).scalar_one() or 0
    return {'count': int(value)}


@router.post('/{notification_id}/read', response_model=NotificationOut)
def mark_read(notification_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Notification not found')

    row.is_read = True
    db.commit()
    db.refresh(row)
    return {
        'id': str(row.id),
        'type': row.type.value,
        'title': row.title,
        'body': row.body,
        'is_read': bool(row.is_read),
        'image_url': row.image_url,
        'deep_link': row.deep_link,
        'created_at': row.created_at.astimezone(timezone.utc).isoformat(),
    }


@router.post('/read-all', status_code=status.HTTP_204_NO_CONTENT)
def mark_read_all(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
    ).scalars().all()

    for row in rows:
        row.is_read = True

    db.commit()
    return None


@router.get('/{notification_id}/links', response_model=list[NotificationLinkOut])
def list_notification_links(notification_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    notification = db.execute(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == current_user.id)
    ).scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Notification not found')

    rows = db.execute(select(NotificationLink).where(NotificationLink.notification_id == notification_id)).scalars().all()
    return [
        {
            'id': str(r.id),
            'notification_id': str(r.notification_id),
            'entity_type': r.entity_type,
            'entity_id': str(r.entity_id),
        }
        for r in rows
    ]


@router.post('/{notification_id}/links', response_model=NotificationLinkOut, status_code=status.HTTP_201_CREATED)
def add_notification_link(
    notification_id: str,
    payload: NotificationLinkIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notification = db.execute(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == current_user.id)
    ).scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Notification not found')

    row = NotificationLink(
        notification_id=notification_id,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        'id': str(row.id),
        'notification_id': str(row.notification_id),
        'entity_type': row.entity_type,
        'entity_id': str(row.entity_id),
    }


@router.delete('/links/{link_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_notification_link(link_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(select(NotificationLink).where(NotificationLink.id == link_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Link not found')

    notification = db.execute(select(Notification).where(Notification.id == row.notification_id)).scalar_one_or_none()
    if not notification or str(notification.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    db.delete(row)
    db.commit()
    return None


@router.post('/push-token', status_code=status.HTTP_204_NO_CONTENT)
def upsert_push_token(payload: PushTokenIn, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    register_push_token(
        db,
        user_id=str(current_user.id),
        platform=payload.platform.strip().lower(),
        token=payload.token.strip(),
    )
    return None


@router.delete('/push-token', status_code=status.HTTP_204_NO_CONTENT)
def remove_push_token(token: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    deactivate_push_token(db, user_id=str(current_user.id), token=token.strip())
    return None
