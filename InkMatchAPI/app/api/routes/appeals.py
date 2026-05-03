from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.enums import AppealTargetType, FileType
from app.schemas.appeal import AppealAttachmentOut, AppealCreateIn, AppealOut
from app.services.appeal_service import (
    add_appeal_attachment,
    create_appeal,
    list_appeal_attachments,
    list_my_appeals,
    serialize_appeal,
    serialize_appeal_attachment,
)
from app.services.media_service import resolve_media_url, upload_media

router = APIRouter()

MAX_APPEAL_ATTACHMENT_BYTES = 20 * 1024 * 1024


def _file_type_from_mime(mime_type: str) -> FileType:
    mime = (mime_type or '').lower()
    if mime.startswith('image/'):
        return FileType.image
    if mime.startswith('video/'):
        return FileType.video
    if mime.startswith('application/') or mime.startswith('text/'):
        return FileType.document
    return FileType.other


@router.get('/me', response_model=list[AppealOut])
def get_my_appeals(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return list_my_appeals(db, str(current_user.id))


@router.post('', response_model=AppealOut, status_code=status.HTTP_201_CREATED)
def create_my_appeal(
    payload: AppealCreateIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        target_type = AppealTargetType(payload.target_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid target_type') from exc

    row = create_appeal(
        db,
        user_id=str(current_user.id),
        target_type=target_type,
        target_id=payload.target_id,
        description=payload.description,
        reason_text=payload.reason_text,
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Appeal target not found')
    db.commit()
    db.refresh(row)
    return serialize_appeal(row)


@router.get('/{appeal_id}/attachments', response_model=list[AppealAttachmentOut])
def get_appeal_attachments(
    appeal_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = list_appeal_attachments(db, appeal_id=appeal_id, user_id=str(current_user.id))
    return rows


@router.post('/{appeal_id}/attachments', response_model=AppealAttachmentOut, status_code=status.HTTP_201_CREATED)
async def upload_appeal_attachment(
    appeal_id: str,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Empty file')
    if len(content) > MAX_APPEAL_ATTACHMENT_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='File size exceeds 20MB limit')

    mime_type = file.content_type or 'application/octet-stream'
    file_type = _file_type_from_mime(mime_type)
    row = add_appeal_attachment(
        db,
        appeal_id=appeal_id,
        user_id=str(current_user.id),
        file_url=upload_media(content, 'appeals', str(current_user.id), mime_type=mime_type),
        file_type=file_type,
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Appeal not found')
    db.commit()
    db.refresh(row)
    return serialize_appeal_attachment(row)
