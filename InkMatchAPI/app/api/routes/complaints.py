from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.enums import NotificationType
from app.schemas.complaint import ComplaintCreateIn, ComplaintOut, ComplaintReasonCategoryOut
from app.services.complaint_service import (
    create_complaint,
    get_reason_catalog,
    list_my_complaints,
    resolve_target_owner_user_id,
    resolve_target_preview_image_url,
)
from app.services.moderation_service import enqueue_complaint_for_moderation, enqueue_suspicious_case_for_complaint
from app.services.notification_service import create_notification

router = APIRouter()


def _to_out(row) -> ComplaintOut:
    return ComplaintOut(
        id=str(row.id),
        target_type=row.target_type,
        target_id=str(row.target_id),
        reason=row.reason,
        details=row.details,
        status=row.status.value,
        created_at=row.created_at,
    )


@router.get('/reasons', response_model=list[ComplaintReasonCategoryOut])
def complaint_reasons(_current_user=Depends(get_current_user)):
    return get_reason_catalog()


@router.post('', response_model=ComplaintOut, status_code=status.HTTP_201_CREATED)
def create_complaint_endpoint(
    payload: ComplaintCreateIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    complaint, error = create_complaint(
        db,
        author_id=str(current_user.id),
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason_code=payload.reason_code,
        details=payload.details,
    )
    if error == 'Target not found':
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)


    enqueue_complaint_for_moderation(
        db,
        complaint_id=str(complaint.id),
        reason_code=payload.reason_code,
    )
    enqueue_suspicious_case_for_complaint(db, str(complaint.id))

    image_url = resolve_target_preview_image_url(db, payload.target_type, payload.target_id)

    create_notification(
        db,
        user_id=str(current_user.id),
        type_=NotificationType.system,
        title='Жалоба отправлена',
        body='Вы успешно отправили жалобу. Мы сообщим о результате.',
        deep_link='/notifications',
        image_url=image_url,
        links=[('complaint', str(complaint.id))],
    )

    target_owner_id = resolve_target_owner_user_id(db, payload.target_type, payload.target_id)
    if target_owner_id and target_owner_id != str(current_user.id):
        create_notification(
            db,
            user_id=target_owner_id,
            type_=NotificationType.system,
            title='Получена жалоба',
            body='На ваш контент подана жалоба. Мы сообщим о результате.',
            deep_link='/notifications',
            image_url=image_url,
            links=[('complaint', str(complaint.id))],
        )

    db.commit()
    return _to_out(complaint)


@router.get('/me', response_model=list[ComplaintOut])
def my_complaints(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = list_my_complaints(db, str(current_user.id), limit=limit, offset=offset)
    return [_to_out(row) for row in rows]
