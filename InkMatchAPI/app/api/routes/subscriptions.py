from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.enums import NotificationType
from app.models.profiles import Profile
from app.services.media_service import resolve_media_url
from app.services.notification_service import create_notification, user_nickname
from app.services.subscription_service import is_subscribed, subscribe, unsubscribe

router = APIRouter()


@router.get('/status')
def subscription_status(
    target_user_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {
        'target_user_id': target_user_id,
        'is_subscribed': is_subscribed(db, str(current_user.id), target_user_id),
    }


@router.post('/{target_user_id}', status_code=status.HTTP_204_NO_CONTENT)
def create_subscription(
    target_user_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ok = subscribe(db, str(current_user.id), target_user_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Cannot subscribe to self')

    actor = user_nickname(db, str(current_user.id))
    actor_avatar = db.execute(
        select(Profile.avatar_url).where(Profile.user_id == current_user.id)
    ).scalar_one_or_none()
    create_notification(
        db,
        user_id=target_user_id,
        type_=NotificationType.system,
        title='Новый подписчик',
        body=f'{actor} подписал(ся) на вас',
        deep_link=f'/profile/{current_user.id}',
        image_url=resolve_media_url(actor_avatar) if actor_avatar else None,
        links=[('user', str(current_user.id))],
    )
    db.commit()
    return None


@router.delete('/{target_user_id}', status_code=status.HTTP_204_NO_CONTENT)
def remove_subscription(
    target_user_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    unsubscribe(db, str(current_user.id), target_user_id)
    return None
