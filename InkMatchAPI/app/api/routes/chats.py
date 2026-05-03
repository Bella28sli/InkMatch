from datetime import timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.enums import FileType, NotificationType, RestrictionType
from app.models.inkmatch import Inkmatch
from app.models.messaging import Chat, ChatParticipant, Message, MessageAttachment, MessageRead
from app.models.profiles import Profile
from app.schemas.chat import ChatListItemOut, DirectChatCreateIn, MessageCreateIn, MessageOut
from app.schemas.engagement import FileAttachmentIn, FileAttachmentOut
from app.services.inkmatch_service import cancel_match_from_chat, confirm_match_from_chat
from app.services.media_service import delete_media_reference, normalize_media_reference, resolve_media_url, upload_media
from app.services.notification_service import create_notification, user_nickname
from app.services.restriction_service import enforce_not_restricted

router = APIRouter()

ROOT_DIR = Path(__file__).resolve().parents[3]
UPLOADS_DIR = ROOT_DIR / 'uploads'


def _assert_participant(db: Session, chat_id: str, user_id: str) -> bool:
    row = db.execute(
        select(ChatParticipant).where(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id == user_id,
        )
    ).scalar_one_or_none()
    return row is not None


def _chat_participant_ids(db: Session, chat_id: str) -> list[str]:
    rows = db.execute(
        select(ChatParticipant.user_id).where(ChatParticipant.chat_id == chat_id)
    ).scalars().all()
    return [str(r) for r in rows]


def _message_status(
    *,
    message: Message,
    current_user_id: str,
    participant_ids: list[str],
    read_by: dict[str, set[str]],
) -> str | None:
    if str(message.sender_id) != str(current_user_id):
        return None

    msg_readers = read_by.get(str(message.id), set())
    others = {pid for pid in participant_ids if pid != str(current_user_id)}
    if others and others.issubset(msg_readers):
        return 'read'
    if others:
        return 'delivered'
    return 'sent'


def _attachments_map(db: Session, message_ids: list[str]) -> dict[str, list[dict]]:
    if not message_ids:
        return {}
    rows = db.execute(
        select(MessageAttachment).where(MessageAttachment.message_id.in_(message_ids))
    ).scalars().all()

    result: dict[str, list[dict]] = {}
    for row in rows:
        msg_id = str(row.message_id)
        result.setdefault(msg_id, []).append(
            {
                'id': str(row.id),
                'file_url': resolve_media_url(row.file_url),
                'file_type': row.file_type.value,
                'mime_type': row.mime_type,
                'file_size_bytes': row.file_size_bytes,
                'width': row.width,
                'height': row.height,
                'duration_seconds': row.duration_seconds,
            }
        )
    return result


def _serialize_messages(
    db: Session,
    *,
    rows: list[Message],
    current_user_id: str,
    chat_id: str,
) -> list[dict]:
    participant_ids = _chat_participant_ids(db, chat_id)
    message_ids = [str(row.id) for row in rows]
    attachments = _attachments_map(db, message_ids)

    reads = db.execute(
        select(MessageRead).where(MessageRead.message_id.in_(message_ids))
    ).scalars().all() if message_ids else []

    read_by: dict[str, set[str]] = {}
    for read in reads:
        read_by.setdefault(str(read.message_id), set()).add(str(read.user_id))

    return [
        {
            'id': str(row.id),
            'chat_id': str(row.chat_id),
            'sender_id': str(row.sender_id) if row.sender_id else None,
            'message_type': row.message_type,
            'text': row.text,
            'payload': row.payload,
            'created_at': row.created_at.astimezone(timezone.utc).isoformat(),
            'message_status': _message_status(
                message=row,
                current_user_id=current_user_id,
                participant_ids=participant_ids,
                read_by=read_by,
            ),
            'attachments': attachments.get(str(row.id), []),
        }
        for row in rows
    ]


def _notify_chat_recipients(db: Session, *, chat_id: str, sender_id: str, body: str, message_id: str) -> None:
    recipient_ids = db.execute(
        select(ChatParticipant.user_id).where(
            ChatParticipant.chat_id == chat_id,
            ChatParticipant.user_id != sender_id,
        )
    ).scalars().all()

    actor = user_nickname(db, sender_id)
    for recipient_id in recipient_ids:
        create_notification(
            db,
            user_id=str(recipient_id),
            type_=NotificationType.message,
            title=f'Новое сообщение от {actor}',
            body=body,
            deep_link=f'/chat/{chat_id}',
            links=[('chat', chat_id), ('message', message_id)],
            in_app=False,
            send_push_too=True,
        )


@router.get('', response_model=list[ChatListItemOut])
def list_chats(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    chat_ids = db.execute(
        select(ChatParticipant.chat_id).where(ChatParticipant.user_id == current_user.id)
    ).scalars().all()
    if not chat_ids:
        return []

    chats = db.execute(
        select(Chat).where(Chat.id.in_(chat_ids)).order_by(Chat.created_at.desc())
    ).scalars().all()

    items = []
    for chat in chats:
        other = db.execute(
            select(ChatParticipant.user_id, Profile.nickname)
            .join(Profile, Profile.user_id == ChatParticipant.user_id)
            .where(
                ChatParticipant.chat_id == chat.id,
                ChatParticipant.user_id != current_user.id,
            )
            .limit(1)
        ).first()

        last_message = db.execute(
            select(Message)
            .where(Message.chat_id == chat.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        unread_count = db.execute(
            select(func.count())
            .select_from(Message)
            .where(
                Message.chat_id == chat.id,
                Message.sender_id.is_not(None),
                Message.sender_id != current_user.id,
                ~select(MessageRead.message_id)
                .where(
                    MessageRead.message_id == Message.id,
                    MessageRead.user_id == current_user.id,
                )
                .exists(),
            )
        ).scalar_one() or 0

        last_message_text = None
        if last_message:
            last_message_text = last_message.text
            if not last_message_text and last_message.message_type == 'file':
                last_message_text = '[Файл]'

        items.append(
            {
                'id': str(chat.id),
                'chat_kind': chat.chat_kind.value,
                'created_at': chat.created_at.astimezone(timezone.utc).isoformat(),
                'other_user_id': str(other[0]) if other else None,
                'other_nickname': other[1] if other else None,
                'last_message_text': last_message_text,
                'last_message_at': (
                    last_message.created_at.astimezone(timezone.utc).isoformat()
                    if last_message
                    else None
                ),
                'unread_count': int(unread_count),
            }
        )
    return items


@router.post('/direct', response_model=ChatListItemOut, status_code=status.HTTP_201_CREATED)
def get_or_create_direct_chat(
    payload: DirectChatCreateIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.chat_only_read)
    if payload.user_id == str(current_user.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Cannot create chat with yourself')

    existing = db.execute(
        select(Chat)
        .join(ChatParticipant, ChatParticipant.chat_id == Chat.id)
        .where(ChatParticipant.user_id == current_user.id)
    ).scalars().all()

    for chat in existing:
        participants = db.execute(
            select(ChatParticipant.user_id).where(ChatParticipant.chat_id == chat.id)
        ).scalars().all()
        participant_ids = {str(p) for p in participants}
        if participant_ids == {str(current_user.id), payload.user_id}:
            other = db.execute(
                select(Profile.nickname).where(Profile.user_id == payload.user_id)
            ).scalar_one_or_none()
            return {
                'id': str(chat.id),
                'chat_kind': chat.chat_kind.value,
                'created_at': chat.created_at.astimezone(timezone.utc).isoformat(),
                'other_user_id': payload.user_id,
                'other_nickname': other,
                'last_message_text': None,
                'last_message_at': None,
                'unread_count': 0,
            }

    try:
        target_user_id = UUID(payload.user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid target user id')

    chat = Chat(created_by_user_id=current_user.id)
    db.add(chat)
    db.flush()
    db.add(ChatParticipant(chat_id=chat.id, user_id=current_user.id))
    db.flush()
    db.add(ChatParticipant(chat_id=chat.id, user_id=target_user_id))
    db.flush()
    db.commit()
    db.refresh(chat)

    other = db.execute(select(Profile.nickname).where(Profile.user_id == payload.user_id)).scalar_one_or_none()
    return {
        'id': str(chat.id),
        'chat_kind': chat.chat_kind.value,
        'created_at': chat.created_at.astimezone(timezone.utc).isoformat(),
        'other_user_id': payload.user_id,
        'other_nickname': other,
        'last_message_text': None,
        'last_message_at': None,
        'unread_count': 0,
    }


@router.get('/{chat_id}/messages', response_model=list[MessageOut])
def list_messages(
    chat_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.chat_only_read)
    if not _assert_participant(db, chat_id, str(current_user.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    unread = db.execute(
        select(Message)
        .where(
            Message.chat_id == chat_id,
            Message.sender_id.is_not(None),
            Message.sender_id != current_user.id,
            ~select(MessageRead.message_id)
            .where(
                MessageRead.message_id == Message.id,
                MessageRead.user_id == current_user.id,
            )
            .exists(),
        )
    ).scalars().all()
    for row in unread:
        db.add(MessageRead(message_id=row.id, user_id=current_user.id))
    if unread:
        db.commit()

    rows = db.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()

    return _serialize_messages(
        db,
        rows=rows,
        current_user_id=str(current_user.id),
        chat_id=chat_id,
    )


@router.post('/{chat_id}/messages', response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def send_message(
    chat_id: str,
    payload: MessageCreateIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.chat_only_read)
    if not _assert_participant(db, chat_id, str(current_user.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    msg = Message(
        chat_id=chat_id,
        sender_id=current_user.id,
        message_type='text',
        text=payload.text.strip(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    _notify_chat_recipients(
        db,
        chat_id=chat_id,
        sender_id=str(current_user.id),
        body=payload.text.strip(),
        message_id=str(msg.id),
    )

    return {
        'id': str(msg.id),
        'chat_id': str(msg.chat_id),
        'sender_id': str(msg.sender_id) if msg.sender_id else None,
        'message_type': msg.message_type,
        'text': msg.text,
        'payload': msg.payload,
        'created_at': msg.created_at.astimezone(timezone.utc).isoformat(),
        'message_status': 'sent',
        'attachments': [],
    }


@router.post('/{chat_id}/messages/with-file', response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def send_message_with_file(
    chat_id: str,
    request: Request,
    file: UploadFile = File(...),
    text: str | None = Form(default=None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _assert_participant(db, chat_id, str(current_user.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    mime_type = file.content_type or 'application/octet-stream'
    if mime_type.startswith('image/'):
        file_type = FileType.image
    elif mime_type.startswith('video/'):
        file_type = FileType.video
    elif mime_type.startswith('application/') or mime_type.startswith('text/'):
        file_type = FileType.document
    else:
        file_type = FileType.other

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Empty file')

    file_url = upload_media(content, 'chat', str(chat_id), mime_type=mime_type)

    message_text = (text or '').strip()
    message_type = 'text' if message_text else 'file'

    msg = Message(
        chat_id=chat_id,
        sender_id=current_user.id,
        message_type=message_type,
        text=message_text or None,
    )
    db.add(msg)
    db.flush()

    attachment = MessageAttachment(
        message_id=msg.id,
        file_url=file_url,
        file_type=file_type,
        mime_type=mime_type,
        file_size_bytes=len(content),
    )
    db.add(attachment)
    db.commit()
    db.refresh(msg)
    db.refresh(attachment)

    _notify_chat_recipients(
        db,
        chat_id=chat_id,
        sender_id=str(current_user.id),
        body=message_text if message_text else '[Файл]',
        message_id=str(msg.id),
    )

    return {
        'id': str(msg.id),
        'chat_id': str(msg.chat_id),
        'sender_id': str(msg.sender_id) if msg.sender_id else None,
        'message_type': msg.message_type,
        'text': msg.text,
        'payload': msg.payload,
        'created_at': msg.created_at.astimezone(timezone.utc).isoformat(),
        'message_status': 'sent',
        'attachments': [
            {
                'id': str(attachment.id),
                'file_url': resolve_media_url(attachment.file_url),
                'file_type': attachment.file_type.value,
                'mime_type': attachment.mime_type,
                'file_size_bytes': attachment.file_size_bytes,
                'width': attachment.width,
                'height': attachment.height,
                'duration_seconds': attachment.duration_seconds,
            }
        ],
    }


@router.get('/messages/{message_id}/attachments', response_model=list[FileAttachmentOut])
def list_message_attachments(message_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    message = db.execute(select(Message).where(Message.id == message_id)).scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Message not found')
    if not _assert_participant(db, str(message.chat_id), str(current_user.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    rows = db.execute(select(MessageAttachment).where(MessageAttachment.message_id == message_id)).scalars().all()
    return [
        {
            'id': str(r.id),
            'file_url': resolve_media_url(r.file_url),
            'file_type': r.file_type.value,
            'mime_type': r.mime_type,
            'file_size_bytes': r.file_size_bytes,
            'width': r.width,
            'height': r.height,
            'duration_seconds': r.duration_seconds,
        }
        for r in rows
    ]


@router.post('/messages/{message_id}/attachments', response_model=FileAttachmentOut, status_code=status.HTTP_201_CREATED)
def add_message_attachment(
    message_id: str,
    payload: FileAttachmentIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.chat_only_read)
    message = db.execute(select(Message).where(Message.id == message_id)).scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Message not found')
    if str(message.sender_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    try:
        file_type = FileType(payload.file_type)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid file_type')

    row = MessageAttachment(
        message_id=message_id,
        file_url=normalize_media_reference(payload.file_url),
        file_type=file_type,
        mime_type=payload.mime_type,
        file_size_bytes=payload.file_size_bytes,
        width=payload.width,
        height=payload.height,
        duration_seconds=payload.duration_seconds,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        'id': str(row.id),
        'file_url': row.file_url,
        'file_type': row.file_type.value,
        'mime_type': row.mime_type,
        'file_size_bytes': row.file_size_bytes,
        'width': row.width,
        'height': row.height,
        'duration_seconds': row.duration_seconds,
    }


@router.delete('/messages/attachments/{attachment_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_message_attachment(attachment_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(select(MessageAttachment).where(MessageAttachment.id == attachment_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Attachment not found')

    message = db.execute(select(Message).where(Message.id == row.message_id)).scalar_one_or_none()
    if not message or str(message.sender_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    delete_media_reference(row.file_url)
    db.delete(row)
    db.commit()
    return None


@router.post('/{chat_id}/inkmatch/{match_id}/confirm', status_code=status.HTTP_200_OK)
def confirm_inkmatch_in_chat(
    chat_id: str,
    match_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.inkmatch_disabled)
    if not _assert_participant(db, chat_id, str(current_user.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    parsed_match_id: str | None = None
    try:
        parsed_match_id = str(UUID(match_id))
    except ValueError:
        parsed_match_id = None

    if parsed_match_id is not None:
        match = db.execute(select(Inkmatch).where(Inkmatch.id == parsed_match_id)).scalar_one_or_none()
    else:
        # Backward compatibility for old system messages where inkmatch_id was "None".
        match = db.execute(
            select(Inkmatch)
            .where(Inkmatch.chat_id == chat_id)
            .order_by(Inkmatch.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='InkMatch not found')
    if str(match.chat_id) != chat_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='InkMatch does not belong to this chat')

    try:
        match = confirm_match_from_chat(db, match, str(current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {
        'id': str(match.id),
        'status': match.status.value,
        'chat_id': str(match.chat_id) if match.chat_id else None,
    }


@router.post('/{chat_id}/inkmatch/{match_id}/cancel', status_code=status.HTTP_204_NO_CONTENT)
def cancel_inkmatch_in_chat(
    chat_id: str,
    match_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.inkmatch_disabled)
    if not _assert_participant(db, chat_id, str(current_user.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    parsed_match_id: str | None = None
    try:
        parsed_match_id = str(UUID(match_id))
    except ValueError:
        parsed_match_id = None

    if parsed_match_id is not None:
        match = db.execute(select(Inkmatch).where(Inkmatch.id == parsed_match_id)).scalar_one_or_none()
    else:
        # Backward compatibility for old system messages where inkmatch_id was "None".
        match = db.execute(
            select(Inkmatch)
            .where(Inkmatch.chat_id == chat_id)
            .order_by(Inkmatch.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='InkMatch not found')
    if str(match.chat_id) != chat_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='InkMatch does not belong to this chat')

    cancel_match_from_chat(db, match)
    return None
