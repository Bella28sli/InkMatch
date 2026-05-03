from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.schemas.engagement import CommentLikeOut, FileAttachmentIn, FileAttachmentOut, PinIn, PinOut
from app.schemas.post import (
    FeedPostOut,
    PostCommentIn,
    PostCommentOut,
    PostDetailOut,
    PostLikeOut,
    PostSaveOut,
)
from app.models.enums import ComplaintTargetType, FileType, ModerationActionType, NotificationType, RestrictionType, UserRole
from app.models.moderation import ModerationAction
from app.models.sketches import CommentAttachment, Sketch, SketchComment, SketchCommentLike, SketchPin
from app.services.media_service import delete_media_reference, normalize_media_reference, resolve_media_url
from app.services.notification_service import create_notification, user_nickname
from app.services.post_service import (
    create_post_comment,
    delete_post_comment,
    get_feed_posts,
    get_post_detail,
    get_similar_posts,
    list_post_comments,
    toggle_post_like,
    toggle_post_save,
)
from app.services.restriction_service import enforce_not_restricted

router = APIRouter()


@router.get('/feed', response_model=list[FeedPostOut])
def get_feed(
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    style_ids: str | None = Query(default=None),
    tag_ids: str | None = Query(default=None),
    q: str | None = Query(default=None),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parsed_style_ids = [v.strip() for v in (style_ids or '').split(',') if v.strip()]
    parsed_tag_ids = [v.strip() for v in (tag_ids or '').split(',') if v.strip()]
    return get_feed_posts(
        db,
        limit,
        offset,
        parsed_style_ids or None,
        parsed_tag_ids or None,
        q,
    )


@router.get('/{post_id}', response_model=PostDetailOut)
def get_post(post_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    payload = get_post_detail(db, post_id, str(current_user.id))
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Post not found')
    return payload


@router.get('/{post_id}/similar', response_model=list[FeedPostOut])
def get_similar(
    post_id: str,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = get_similar_posts(db, post_id, limit=limit, offset=offset)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Post not found')
    return payload


@router.post('/{post_id}/like-toggle', response_model=PostLikeOut)
def like_toggle(post_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    payload = toggle_post_like(db, post_id, str(current_user.id))
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Post not found')
    return payload


@router.get('/{post_id}/comments', response_model=list[PostCommentOut])
def get_comments(post_id: str, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return list_post_comments(db, post_id)


@router.post('/{post_id}/comments', response_model=PostCommentOut, status_code=status.HTTP_201_CREATED)
def create_comment(
    post_id: str,
    payload: PostCommentIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.commenting_disabled)
    row = create_post_comment(db, post_id, str(current_user.id), payload.body, payload.parent_comment_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Post not found')
    if row == 'parent_not_found':
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Parent comment not found')
    return row


@router.delete('/comments/{comment_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    comment = db.execute(select(SketchComment).where(SketchComment.id == comment_id)).scalar_one_or_none()
    sketch = None
    if comment:
        sketch = db.execute(select(Sketch).where(Sketch.id == comment.sketch_id)).scalar_one_or_none()
    error = delete_post_comment(
        db,
        comment_id,
        str(current_user.id),
        allow_moderator=current_user.role == UserRole.moderator,
    )
    if error == 'not_found':
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Comment not found')
    if error == 'forbidden':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')
    if comment and sketch and current_user.role == UserRole.moderator:
        image_url = db.execute(
            select(SketchMedia.url)
            .where(SketchMedia.sketch_id == sketch.id)
            .order_by(SketchMedia.sort_order.asc())
            .limit(1)
        ).scalar_one_or_none()
        db.add(
            ModerationAction(
                moderator_id=current_user.id,
                action_type=ModerationActionType.remove_content,
                target_type=ComplaintTargetType.comment,
                target_id=comment.id,
                reason='comment_deleted_by_moderator',
                params={'sketch_id': str(sketch.id), 'author_user_id': str(comment.author_user_id)},
            )
        )
        create_notification(
            db,
            user_id=str(comment.author_user_id),
            type_=NotificationType.moderation,
            title='Комментарий удалён',
            body='Модератор удалил ваш комментарий.',
            deep_link=f'/post/{sketch.id}',
            image_url=image_url,
            links=[('sketch', str(sketch.id)), ('comment', str(comment.id))],
        )
        db.commit()
    return None


@router.post('/{post_id}/save-toggle', response_model=PostSaveOut)
def save_toggle(post_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    payload = toggle_post_save(db, post_id, str(current_user.id))
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Post not found')
    return payload


@router.get('/comments/{comment_id}/attachments', response_model=list[FileAttachmentOut])
def get_comment_attachments(comment_id: str, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(CommentAttachment).where(CommentAttachment.comment_id == comment_id)
    ).scalars().all()
    return [
        {
            'id': str(r.id),
            'file_url': resolve_media_url(r.file_url),
            'file_type': r.file_type.value,
            'mime_type': r.mime_type,
            'file_size_bytes': r.file_size_bytes,
            'width': r.width,
            'height': r.height,
            'duration_seconds': None,
        }
        for r in rows
    ]


@router.post('/comments/{comment_id}/attachments', response_model=FileAttachmentOut, status_code=status.HTTP_201_CREATED)
def add_comment_attachment(
    comment_id: str,
    payload: FileAttachmentIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.commenting_disabled)
    comment = db.execute(select(SketchComment).where(SketchComment.id == comment_id)).scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Comment not found')
    if str(comment.author_user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    try:
        file_type = FileType(payload.file_type)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid file_type')

    row = CommentAttachment(
        comment_id=comment_id,
        file_url=normalize_media_reference(payload.file_url),
        file_type=file_type,
        mime_type=payload.mime_type,
        file_size_bytes=payload.file_size_bytes,
        width=payload.width,
        height=payload.height,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        'id': str(row.id),
        'file_url': resolve_media_url(row.file_url),
        'file_type': row.file_type.value,
        'mime_type': row.mime_type,
        'file_size_bytes': row.file_size_bytes,
        'width': row.width,
        'height': row.height,
        'duration_seconds': None,
    }


@router.delete('/comments/attachments/{attachment_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_comment_attachment(attachment_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(select(CommentAttachment).where(CommentAttachment.id == attachment_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Attachment not found')
    comment = db.execute(select(SketchComment).where(SketchComment.id == row.comment_id)).scalar_one_or_none()
    if not comment or str(comment.author_user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')
    delete_media_reference(row.file_url)
    db.delete(row)
    db.commit()
    return None


@router.post('/comments/{comment_id}/like-toggle', response_model=CommentLikeOut)
def like_comment(comment_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    comment = db.execute(select(SketchComment).where(SketchComment.id == comment_id)).scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Comment not found')

    row = db.execute(
        select(SketchCommentLike).where(
            SketchCommentLike.comment_id == comment_id,
            SketchCommentLike.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if row:
        db.delete(row)
        is_liked = False
    else:
        db.add(SketchCommentLike(comment_id=comment_id, user_id=current_user.id))
        is_liked = True
    db.commit()

    if is_liked and str(comment.author_user_id) != str(current_user.id):
        actor = user_nickname(db, str(current_user.id))
        image_url = db.execute(
            select(SketchMedia.url)
            .where(SketchMedia.sketch_id == comment.sketch_id)
            .order_by(SketchMedia.sort_order.asc())
            .limit(1)
        ).scalar_one_or_none()
        create_notification(
            db,
            user_id=str(comment.author_user_id),
            type_=NotificationType.system,
            title='Комментарий понравился',
            body=f'{actor} оценил(а) ваш комментарий',
            deep_link=f'/post/{comment.sketch_id}',
            image_url=image_url,
            links=[('comment', comment_id), ('sketch', str(comment.sketch_id))],
        )
        db.commit()

    likes_count = db.execute(
        select(func.count()).select_from(SketchCommentLike).where(SketchCommentLike.comment_id == comment_id)
    ).scalar_one() or 0
    return {'comment_id': comment_id, 'likes_count': int(likes_count), 'is_liked': is_liked}


@router.get('/{post_id}/pin', response_model=PinOut | None)
def get_post_pin(post_id: str, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(select(SketchPin).where(SketchPin.sketch_id == post_id)).scalar_one_or_none()
    if not row:
        return None
    return {
        'sketch_id': str(row.sketch_id),
        'pinned_comment_id': str(row.pinned_comment_id),
        'pinned_by_user_id': str(row.pinned_by_user_id),
        'pinned_reason': row.pinned_reason,
    }


@router.put('/{post_id}/pin', response_model=PinOut)
def set_post_pin(
    post_id: str,
    payload: PinIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sketch = db.execute(select(Sketch).where(Sketch.id == post_id)).scalar_one_or_none()
    if not sketch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Post not found')
    if str(sketch.author_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    comment = db.execute(
        select(SketchComment).where(
            SketchComment.id == payload.comment_id,
            SketchComment.sketch_id == post_id,
        )
    ).scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Comment not found')

    row = db.execute(select(SketchPin).where(SketchPin.sketch_id == post_id)).scalar_one_or_none()
    if not row:
        row = SketchPin(
            sketch_id=post_id,
            pinned_comment_id=payload.comment_id,
            pinned_by_user_id=current_user.id,
            pinned_reason=payload.pinned_reason,
        )
        db.add(row)
    else:
        row.pinned_comment_id = payload.comment_id
        row.pinned_by_user_id = current_user.id
        row.pinned_reason = payload.pinned_reason

    db.commit()

    if str(comment.author_user_id) != str(current_user.id):
        actor = user_nickname(db, str(current_user.id))
        create_notification(
            db,
            user_id=str(comment.author_user_id),
            type_=NotificationType.system,
            title='Комментарий к посту',
            body=f'{actor} оставил(а) комментарий к вашему посту',
            deep_link=f'/post/{post_id}',
            links=[('comment', payload.comment_id), ('sketch', post_id)],
        )
        db.commit()

    return {
        'sketch_id': str(row.sketch_id),
        'pinned_comment_id': str(row.pinned_comment_id),
        'pinned_by_user_id': str(row.pinned_by_user_id),
        'pinned_reason': row.pinned_reason,
    }


@router.delete('/{post_id}/pin', status_code=status.HTTP_204_NO_CONTENT)
def delete_post_pin(post_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    sketch = db.execute(select(Sketch).where(Sketch.id == post_id)).scalar_one_or_none()
    if not sketch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Post not found')
    if str(sketch.author_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    row = db.execute(select(SketchPin).where(SketchPin.sketch_id == post_id)).scalar_one_or_none()
    if row:
        db.delete(row)
        db.commit()
    return None
