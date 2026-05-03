from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import (
    DocumentType,
    ModerationQueueEntityType,
    ModerationQueueStatus,
    NotificationType,
    UserRole,
    VerificationStatus,
)
from app.models.moderation import ModerationQueueItem
from app.models.messaging import Notification
from app.models.profiles import MasterProfile
from app.models.user import User
from app.models.verification import (
    MasterVerificationDocument,
    MasterVerificationDocumentFile,
    MasterVerificationPersonalData,
    MasterVerificationRequest,
)
from app.services.media_service import delete_media_reference, resolve_media_url, upload_media
from app.services.notification_service import create_notification


def _latest_request(db: Session, master_id: str) -> MasterVerificationRequest | None:
    return db.execute(
        select(MasterVerificationRequest)
        .where(MasterVerificationRequest.master_id == master_id)
        .order_by(MasterVerificationRequest.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _first_moderator_id(db: Session) -> str | None:
    row = db.execute(
        select(User.id).where(User.role == UserRole.moderator).order_by(User.id.asc()).limit(1)
    ).scalar_one_or_none()
    return str(row) if row else None


def _enqueue_verification_for_moderation(db: Session, request: MasterVerificationRequest) -> ModerationQueueItem:
    existing = db.execute(
        select(ModerationQueueItem).where(
            ModerationQueueItem.entity_type == ModerationQueueEntityType.verification,
            ModerationQueueItem.entity_id == request.id,
            ModerationQueueItem.status.in_([ModerationQueueStatus.open, ModerationQueueStatus.in_progress]),
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    moderator_uuid = None
    moderator_id = _first_moderator_id(db)
    if moderator_id:
        try:
            from uuid import UUID

            moderator_uuid = UUID(moderator_id)
        except (TypeError, ValueError):
            moderator_uuid = None

    row = ModerationQueueItem(
        entity_type=ModerationQueueEntityType.verification,
        entity_id=request.id,
        priority=2,
        status=ModerationQueueStatus.open,
        assigned_moderator_id=moderator_uuid,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _create_request(db: Session, master_id: str) -> MasterVerificationRequest:
    request = MasterVerificationRequest(master_id=master_id)
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def get_verification_request_payload(db: Session, master_id: str) -> dict[str, Any]:
    request = _latest_request(db, master_id)
    if request is None:
        return {
            'request_id': None,
            'status': VerificationStatus.draft.value,
            'comments': None,
            'rejection_reason': None,
            'submitted_at': None,
            'reviewed_at': None,
            'personal_data': None,
            'documents': [],
        }

    personal_data = db.execute(
        select(MasterVerificationPersonalData)
        .where(MasterVerificationPersonalData.request_id == request.id)
    ).scalar_one_or_none()

    attachments = db.execute(
        select(MasterVerificationDocumentFile, MasterVerificationDocument)
        .join(MasterVerificationDocument, MasterVerificationDocument.id == MasterVerificationDocumentFile.document_id)
        .where(MasterVerificationDocument.request_id == request.id)
        .order_by(MasterVerificationDocument.created_at.asc(), MasterVerificationDocumentFile.created_at.asc())
    ).all()

    documents = []
    for file_row, document_row in attachments:
        normalized_type = _normalize_document_type(document_row.document_type.value)
        title = document_row.title or _document_type_label(normalized_type)
        documents.append(
            {
                'id': str(file_row.id),
                'document_id': str(document_row.id),
                'document_type': normalized_type,
                'title': title,
                'issuer': document_row.issuer,
                'issued_date': document_row.issued_date.isoformat() if document_row.issued_date else None,
                'file_url': resolve_media_url(file_row.file_url),
                'file_type': file_row.file_type,
                'created_at': file_row.created_at.isoformat(),
            }
        )

    return {
        'request_id': str(request.id),
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


def _normalize_document_type(document_type: str) -> str:
    if document_type in {DocumentType.id.value, DocumentType.passport.value}:
        return 'identity_document'
    return document_type


def _document_type_label(document_type: str) -> str:
    return {
        'identity_document': 'Identity document',
        DocumentType.certificate.value: 'Certificate',
        DocumentType.diploma.value: 'Diploma',
        DocumentType.award.value: 'Award',
        DocumentType.other.value: 'Other',
    }.get(document_type, document_type)


def upsert_personal_data(db: Session, master_id: str, data: dict[str, Any]) -> MasterVerificationRequest:
    request = _latest_request(db, master_id)
    if request is None:
        request = _create_request(db, master_id)

    if request.status == VerificationStatus.approved:
        raise ValueError('Verification request already approved')

    personal_data = db.execute(
        select(MasterVerificationPersonalData).where(MasterVerificationPersonalData.request_id == request.id)
    ).scalar_one_or_none()
    if not personal_data:
        personal_data = MasterVerificationPersonalData(request_id=request.id, **data)
        db.add(personal_data)
    else:
        for key, value in data.items():
            setattr(personal_data, key, value)
    db.commit()
    db.refresh(request)
    return request


def submit_verification_request(db: Session, master_id: str) -> MasterVerificationRequest:
    request = _latest_request(db, master_id)
    if request is None:
        raise ValueError('Verification request not found')
    if request.status == VerificationStatus.approved:
        raise ValueError('Verification already approved')

    passport_count = db.execute(
        select(MasterVerificationDocument)
        .where(
            MasterVerificationDocument.request_id == request.id,
            MasterVerificationDocument.document_type.in_([DocumentType.passport, DocumentType.id]),
        )
        .limit(1)
    ).scalar_one_or_none()
    if passport_count is None:
        raise ValueError('Passport document is required')

    request.status = VerificationStatus.submitted
    request.submitted_at = datetime.now(request.submitted_at.tzinfo) if request.submitted_at else datetime.now()
    request.rejection_reason = None
    db.commit()
    db.refresh(request)

    _enqueue_verification_for_moderation(db, request)
    return request


def skip_verification_request(db: Session, master_id: str) -> MasterVerificationRequest:
    """Mark verification as skipped by the user."""
    request = _latest_request(db, master_id)
    if request is None:
        request = _create_request(db, master_id)
    
    if request.status == VerificationStatus.approved:
        raise ValueError('Verification already approved')

    request.status = VerificationStatus.skipped
    profile = db.execute(
        select(MasterProfile).where(MasterProfile.user_id == master_id)
    ).scalar_one_or_none()
    if profile:
        profile.verification_skipped = True

    db.commit()
    db.refresh(request)
    
    return request


def upload_verification_document(
    db: Session,
    master_id: str,
    document_type: str,
    title: str | None,
    issuer: str | None,
    issued_date: date | None,
    content: bytes,
    mime_type: str,
) -> tuple[MasterVerificationDocumentFile, MasterVerificationDocument]:
    try:
        document_type_enum = DocumentType(document_type)
    except ValueError as exc:
        raise ValueError('Invalid document_type') from exc

    if document_type_enum in {DocumentType.id, DocumentType.passport}:
        document_type_enum = DocumentType.passport

    request = _latest_request(db, master_id)
    if request is None:
        request = _create_request(db, master_id)
    if request.status == VerificationStatus.approved:
        raise ValueError('Verification already approved')

    document = MasterVerificationDocument(
        request_id=request.id,
        document_type=document_type_enum,
        title=title or _document_type_label(_normalize_document_type(document_type_enum.value)),
        issuer=issuer,
        issued_date=issued_date,
    )
    db.add(document)
    db.flush()

    file_url = upload_media(content, 'verification', str(master_id), mime_type=mime_type)
    file_row = MasterVerificationDocumentFile(
        document_id=document.id,
        file_url=file_url,
        file_type=mime_type,
    )
    db.add(file_row)
    db.commit()
    db.refresh(file_row)
    db.refresh(document)
    return file_row, document


def delete_verification_document_file(db: Session, master_id: str, document_file_id: str) -> bool:
    row = db.execute(
        select(MasterVerificationDocumentFile, MasterVerificationDocument)
        .join(MasterVerificationDocument, MasterVerificationDocument.id == MasterVerificationDocumentFile.document_id)
        .where(MasterVerificationDocumentFile.id == document_file_id)
    ).first()
    if not row:
        return False
    file_row, document_row = row
    request = db.execute(
        select(MasterVerificationRequest).where(MasterVerificationRequest.id == document_row.request_id)
    ).scalar_one_or_none()
    if not request or request.master_id != master_id:
        return False

    delete_media_reference(file_row.file_url)
    db.delete(file_row)
    db.commit()
    return True


def send_weekly_unverified_master_reminders(db: Session) -> int:
    reminder_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    rows = db.execute(
        select(User.id)
        .join(MasterProfile, MasterProfile.user_id == User.id)
        .where(User.role == UserRole.master, MasterProfile.is_verified.is_(False))
    ).scalars().all()
    count = 0
    for user_id in rows:
        recent_reminder = db.execute(
            select(Notification.id)
            .where(
                Notification.user_id == user_id,
                Notification.type == NotificationType.system,
                Notification.deep_link == '/master-verification',
                Notification.created_at >= reminder_cutoff,
            )
            .limit(1)
        ).scalar_one_or_none()
        if recent_reminder:
            continue
        create_notification(
            db,
            user_id=str(user_id),
            type_=NotificationType.system,
            title='Проверка аккаунта мастера',
            body='Вы еще не подтвердили свой аккаунт мастера. Пройдите верификацию, чтобы получить отметку на профиле.',
            deep_link='/master-verification',
            send_push_too=True,
            in_app=True,
        )
        count += 1
    db.commit()
    return count
