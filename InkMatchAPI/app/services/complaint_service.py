from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ComplaintTargetType
from app.models.inkmatch import Inkmatch, InkmatchRequest, InkmatchReview
from app.models.messaging import Message, MessageAttachment
from app.models.moderation import Complaint
from app.models.sketches import Sketch, SketchComment, SketchMedia
from app.models.user import User

COMPLAINT_REASON_CATALOG = [
    {
        'code': 'abuse',
        'title': 'Оскорбления и агрессия',
        'reasons': [
            {'code': 'insult', 'title': 'Оскорбление', 'description': 'Оскорбления, унижение, травля.'},
            {'code': 'hate_speech', 'title': 'Язык ненависти', 'description': 'Агрессия по признаку пола/расы и т.п.'},
            {'code': 'threats', 'title': 'Угрозы', 'description': 'Угрозы жизни или здоровью.'},
        ],
    },
    {
        'code': 'safety',
        'title': 'Безопасность и незаконный контент',
        'reasons': [
            {'code': 'violence', 'title': 'Насилие', 'description': 'Призывы к насилию или жестокий контент.'},
            {'code': 'self_harm', 'title': 'Самоповреждение', 'description': 'Контент о самоповреждении без предупреждений.'},
            {'code': 'illegal_services', 'title': 'Незаконные услуги', 'description': 'Продажа/покупка запрещенных услуг.'},
        ],
    },
    {
        'code': 'fraud',
        'title': 'Мошенничество и спам',
        'reasons': [
            {'code': 'scam', 'title': 'Мошенничество', 'description': 'Обман, выманивание денег или данных.'},
            {'code': 'spam', 'title': 'Спам', 'description': 'Навязчивая реклама или массовые повторяющиеся сообщения.'},
            {'code': 'impersonation', 'title': 'Выдача себя за другого', 'description': 'Аккаунт притворяется другим человеком.'},
        ],
    },
    {
        'code': 'adult',
        'title': 'Неприемлемый контент',
        'reasons': [
            {'code': 'adult_content', 'title': 'Контент для взрослых', 'description': 'Явные изображения или описания.'},
            {'code': 'shocking', 'title': 'Шок-контент', 'description': 'Откровенно отталкивающий материал.'},
        ],
    },
    {
        'code': 'copyright',
        'title': 'Права и конфиденциальность',
        'reasons': [
            {'code': 'copyright_violation', 'title': 'Нарушение авторских прав', 'description': 'Использование чужих работ без разрешения.'},
            {'code': 'privacy_violation', 'title': 'Нарушение приватности', 'description': 'Публикация личных данных без согласия.'},
        ],
    },
    {
        'code': 'other',
        'title': 'Другое',
        'reasons': [
            {'code': 'other', 'title': 'Другая причина', 'description': 'Опишите проблему в комментарии.'},
        ],
    },
]

_REASON_INDEX = {
    reason["code"]: reason
    for category in COMPLAINT_REASON_CATALOG
    for reason in category["reasons"]
}


def get_reason_catalog() -> list[dict]:
    return COMPLAINT_REASON_CATALOG


def get_reason_by_code(reason_code: str) -> dict | None:
    return _REASON_INDEX.get(reason_code)


def _parse_uuid(raw_id: str) -> UUID | None:
    try:
        return UUID(raw_id)
    except (TypeError, ValueError):
        return None


def target_exists(db: Session, target_type: ComplaintTargetType, target_id: str) -> bool:
    target_uuid = _parse_uuid(target_id)
    if not target_uuid:
        return False

    model_map = {
        ComplaintTargetType.user: User,
        ComplaintTargetType.sketch: Sketch,
        ComplaintTargetType.message: Message,
        ComplaintTargetType.comment: SketchComment,
        ComplaintTargetType.review: InkmatchReview,
    }
    model = model_map[target_type]
    row = db.execute(select(model.id).where(model.id == target_uuid)).scalar_one_or_none()
    return row is not None


def create_complaint(
    db: Session,
    *,
    author_id: str,
    target_type: ComplaintTargetType,
    target_id: str,
    reason_code: str,
    details: str | None,
) -> tuple[Complaint | None, str | None]:
    reason = get_reason_by_code(reason_code)
    if not reason:
        return None, "Unknown reason_code"

    if not target_exists(db, target_type, target_id):
        return None, "Target not found"

    target_uuid = _parse_uuid(target_id)
    if not target_uuid:
        return None, "Invalid target_id"

    complaint = Complaint(
        author_id=author_id,
        target_type=target_type,
        target_id=target_uuid,
        reason=reason["title"],
        details=details,
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)
    return complaint, None


def list_my_complaints(db: Session, author_id: str, *, limit: int, offset: int) -> list[Complaint]:
    stmt = (
        select(Complaint)
        .where(Complaint.author_id == author_id)
        .order_by(Complaint.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return db.execute(stmt).scalars().all()


def resolve_target_owner_user_id(db: Session, target_type: ComplaintTargetType, target_id: str) -> str | None:
    target_uuid = _parse_uuid(target_id)
    if not target_uuid:
        return None

    if target_type == ComplaintTargetType.user:
        row = db.execute(select(User.id).where(User.id == target_uuid)).scalar_one_or_none()
        return str(row) if row else None

    if target_type == ComplaintTargetType.sketch:
        row = db.execute(select(Sketch.author_id).where(Sketch.id == target_uuid)).scalar_one_or_none()
        return str(row) if row else None

    if target_type == ComplaintTargetType.message:
        row = db.execute(select(Message.sender_id).where(Message.id == target_uuid)).scalar_one_or_none()
        return str(row) if row else None

    if target_type == ComplaintTargetType.comment:
        row = db.execute(select(SketchComment.author_user_id).where(SketchComment.id == target_uuid)).scalar_one_or_none()
        return str(row) if row else None

    if target_type == ComplaintTargetType.review:
        review = db.execute(select(InkmatchReview).where(InkmatchReview.id == target_uuid)).scalar_one_or_none()
        if not review:
            return None
        match = db.execute(select(Inkmatch).where(Inkmatch.id == review.inkmatch_id)).scalar_one_or_none()
        if not match:
            return None
        master_req = db.execute(select(InkmatchRequest).where(InkmatchRequest.id == match.master_request_id)).scalar_one_or_none()
        if not master_req:
            return None
        return str(master_req.created_by_user_id)

    return None


def resolve_target_preview_image_url(db: Session, target_type: ComplaintTargetType, target_id: str) -> str | None:
    target_uuid = _parse_uuid(target_id)
    if not target_uuid:
        return None

    if target_type == ComplaintTargetType.sketch:
        return db.execute(
            select(SketchMedia.url)
            .where(SketchMedia.sketch_id == target_uuid)
            .order_by(SketchMedia.sort_order.asc())
            .limit(1)
        ).scalar_one_or_none()

    if target_type == ComplaintTargetType.comment:
        comment = db.execute(select(SketchComment).where(SketchComment.id == target_uuid)).scalar_one_or_none()
        if not comment:
            return None
        return db.execute(
            select(SketchMedia.url)
            .where(SketchMedia.sketch_id == comment.sketch_id)
            .order_by(SketchMedia.sort_order.asc())
            .limit(1)
        ).scalar_one_or_none()

    if target_type == ComplaintTargetType.message:
        attachment = db.execute(
            select(MessageAttachment)
            .where(MessageAttachment.message_id == target_uuid)
            .order_by(MessageAttachment.created_at.asc())
            .limit(1)
        ).scalar_one_or_none()
        if attachment and attachment.file_type.value == 'image':
            return attachment.file_url

    return None
