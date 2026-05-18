from datetime import timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.enums import CollectionType, MediaType, OriginalAuthorType, RestrictionType, SketchContentType, UserRole
from app.models.sketches import Collection, CollectionItem, Sketch, SketchMedia, SketchStyle, SketchTag
from app.services.collection_service import ensure_my_posts_collection
from app.models.user import User
from app.services.image_hash_service import compute_phash
from app.services.media_service import delete_media_reference, normalize_media_reference, resolve_media_url, upload_media
from app.services.moderation_service import enqueue_new_post_for_moderation
from app.services.restriction_service import enforce_not_restricted
from app.schemas.sketch import SketchCreateIn, SketchDetailOut, SketchListItemOut, SketchRefsIn, SketchUpdateIn

router = APIRouter()

ALLOWED_MEDIA_MIME = {'image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/heic', 'image/heif'}


CLIENT_ALLOWED_CONTENT_TYPES = {SketchContentType.sketch, SketchContentType.final_work}
MASTER_COLLECTION_BY_CONTENT_TYPE = {
    SketchContentType.portfolio: CollectionType.portfolio,
    SketchContentType.process: CollectionType.process,
    SketchContentType.materials: CollectionType.materials,
    SketchContentType.find_us: CollectionType.find_us,
    SketchContentType.achievments: CollectionType.achievments,
    SketchContentType.final_work: CollectionType.portfolio,
}


def _ensure_master_collection(db: Session, owner_id: str, collection_type: CollectionType) -> Collection:
    existing = db.execute(
        select(Collection).where(
            Collection.owner_id == owner_id,
            Collection.collection_type == collection_type,
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    title_map = {
        CollectionType.portfolio: 'Портфолио',
        CollectionType.process: 'Процесс',
        CollectionType.materials: 'Материалы',
        CollectionType.find_us: 'Как нас найти',
        CollectionType.achievments: 'Достижения',
    }
    row = Collection(
        owner_id=owner_id,
        collection_type=collection_type,
        title=title_map.get(collection_type, collection_type.value.title()),
        description='',
        is_system=True,
        is_private=False,
    )
    db.add(row)
    db.flush()
    return row

@router.post('/upload-media')
async def upload_sketch_media(
    request: Request,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.posting_disabled)
    mime_type = (file.content_type or '').lower()
    ext = Path(file.filename or '').suffix.lower()
    if mime_type not in ALLOWED_MEDIA_MIME and ext not in {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Unsupported media type. Use jpeg/png/webp/heic.',
        )

    ext_map = {
        'image/jpeg': '.jpg',
        'image/jpg': '.jpg',
        'image/png': '.png',
        'image/webp': '.webp',
        'image/heic': '.heic',
        'image/heif': '.heif',
    }
    ext = ext_map.get(mime_type, ext or '.jpg')

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Empty file')

    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Media size exceeds 20MB limit')

    phash = compute_phash(content)

    media_ref = upload_media(
        content,
        'sketches',
        str(current_user.id),
        mime_type=mime_type,
        file_ext=ext,
    )

    if not media_ref:
        raise HTTPException(
            status_code=500,
            detail='upload_media returned empty value',
        )

    return {
        'url': media_ref,
        'resolved_url': resolve_media_url(media_ref),
        'phash': phash,
    }


def _sketch_to_detail(db: Session, row: Sketch):
    media_urls = [resolve_media_url(url) for url in list(
        db.execute(
            select(SketchMedia.url)
            .where(SketchMedia.sketch_id == row.id)
            .order_by(SketchMedia.sort_order.asc())
        ).scalars().all()
    )]
    return {
        'id': str(row.id),
        'author_id': str(row.author_id),
        'title': row.title,
        'description': row.description,
        'content_type': row.content_type.value,
        'feed_visibility': row.feed_visibility,
        'created_at': row.created_at.astimezone(timezone.utc).isoformat(),
        'updated_at': row.updated_at.astimezone(timezone.utc).isoformat(),
        'like_amount': int(row.like_amount or 0),
        'media_urls': media_urls,
    }


@router.get('/me', response_model=list[SketchListItemOut])
def list_my_sketches(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(Sketch)
        .where(Sketch.author_id == current_user.id)
        .order_by(Sketch.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()

    items = []
    for row in rows:
        preview = db.execute(
            select(SketchMedia.url)
            .where(SketchMedia.sketch_id == row.id)
            .order_by(SketchMedia.sort_order.asc())
            .limit(1)
        ).scalar_one_or_none()
        items.append(
            {
                'id': str(row.id),
                'author_id': str(row.author_id),
                'title': row.title,
                'description': row.description,
                'content_type': row.content_type.value,
                'feed_visibility': row.feed_visibility,
                'created_at': row.created_at.astimezone(timezone.utc).isoformat(),
                'like_amount': int(row.like_amount or 0),
                'preview_url': preview,
            }
        )
    return items


@router.post('', response_model=SketchDetailOut, status_code=status.HTTP_201_CREATED)
def create_sketch(payload: SketchCreateIn, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.posting_disabled)
    try:
        content_type = SketchContentType(payload.content_type)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid content_type')

    author = db.execute(select(User).where(User.id == current_user.id)).scalar_one_or_none()
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    if author.role == UserRole.client and content_type not in CLIENT_ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Client can publish only sketch/final_work content types',
        )

    row = Sketch(
        author_id=current_user.id,
        content_type=content_type,
        feed_visibility=payload.feed_visibility,
        title=payload.title,
        description=payload.description,
        original_author_type=OriginalAuthorType.self_,
        like_amount=0,
        reviewed=False,
    )
    db.add(row)
    db.flush()

    media_items = payload.media_items or [{'url': url, 'phash': None} for url in payload.media_urls]
    for index, media_item in enumerate(media_items):
        media_url = media_item.url if hasattr(media_item, 'url') else media_item['url']
        phash = media_item.phash if hasattr(media_item, 'phash') else media_item.get('phash')
        clean_url = normalize_media_reference(media_url.strip())
        if not clean_url:
            continue
        db.add(
            SketchMedia(
                sketch_id=row.id,
                media_type=MediaType.image,
                url=clean_url,
                sha256=sha256(clean_url.encode('utf-8')).hexdigest(),
                phash=phash[:16] if phash else None,
                sort_order=index,
            )
        )

    if author.role == UserRole.master:
        target_collection_type = MASTER_COLLECTION_BY_CONTENT_TYPE.get(content_type)
        if target_collection_type is not None:
            collection = _ensure_master_collection(db, str(current_user.id), target_collection_type)
            has_item = db.execute(
                select(CollectionItem).where(
                    CollectionItem.collection_id == collection.id,
                    CollectionItem.sketch_id == row.id,
                )
            ).scalar_one_or_none()
            if not has_item:
                next_order = db.execute(
                    select(func.coalesce(func.max(CollectionItem.sort_order), 0)).where(
                        CollectionItem.collection_id == collection.id
                    )
                ).scalar_one()
                db.add(
                    CollectionItem(
                        collection_id=collection.id,
                        sketch_id=row.id,
                        sort_order=int(next_order) + 1,
                    )
                )

    target_collection_id = payload.collection_id
    if target_collection_id:
        selected_collection = db.execute(
            select(Collection).where(
                Collection.id == target_collection_id,
                Collection.owner_id == current_user.id,
            )
        ).scalar_one_or_none()
        if selected_collection:
            next_order = db.execute(
                select(func.coalesce(func.max(CollectionItem.sort_order), 0)).where(
                    CollectionItem.collection_id == selected_collection.id
                )
            ).scalar_one()
            db.add(
                CollectionItem(
                    collection_id=selected_collection.id,
                    sketch_id=row.id,
                    sort_order=int(next_order) + 1,
                )
            )

    my_posts = ensure_my_posts_collection(db, str(current_user.id))
    has_item = db.execute(
        select(CollectionItem).where(
            CollectionItem.collection_id == my_posts.id,
            CollectionItem.sketch_id == row.id,
        )
    ).scalar_one_or_none()
    if not has_item:
        next_order = db.execute(
            select(func.coalesce(func.max(CollectionItem.sort_order), 0)).where(
                CollectionItem.collection_id == my_posts.id
            )
        ).scalar_one()
        db.add(
            CollectionItem(
                collection_id=my_posts.id,
                sketch_id=row.id,
                sort_order=int(next_order) + 1,
            )
        )

    enqueue_new_post_for_moderation(db, str(row.id))
    db.commit()
    db.refresh(row)
    return _sketch_to_detail(db, row)


@router.get('/{sketch_id}', response_model=SketchDetailOut)
def get_sketch(sketch_id: str, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(select(Sketch).where(Sketch.id == sketch_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Интересующий вас объект был удалён',
        )
    return _sketch_to_detail(db, row)


@router.patch('/{sketch_id}', response_model=SketchDetailOut)
def update_sketch(
    sketch_id: str,
    payload: SketchUpdateIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.posting_disabled)
    row = db.execute(select(Sketch).where(Sketch.id == sketch_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Интересующий вас объект был удалён',
        )
    if str(row.author_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    if payload.title is not None:
        row.title = payload.title
    if payload.description is not None:
        row.description = payload.description
    if payload.feed_visibility is not None:
        row.feed_visibility = payload.feed_visibility

    db.commit()
    db.refresh(row)
    return _sketch_to_detail(db, row)


@router.delete('/{sketch_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_sketch(sketch_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.posting_disabled)
    row = db.execute(select(Sketch).where(Sketch.id == sketch_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Интересующий вас объект был удалён',
        )
    if str(row.author_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    media_urls = db.execute(select(SketchMedia.url).where(SketchMedia.sketch_id == row.id)).scalars().all()
    for media_url in media_urls:
        delete_media_reference(media_url)

    # Dependent rows are removed by database cascades.
    db.delete(row)
    db.commit()
    return None


@router.get('/{sketch_id}/styles', response_model=list[str])
def get_sketch_styles(sketch_id: str, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(SketchStyle.style_id).where(SketchStyle.sketch_id == sketch_id)).scalars().all()
    return [str(r) for r in rows]


@router.put('/{sketch_id}/styles', response_model=list[str])
def set_sketch_styles(
    sketch_id: str,
    payload: SketchRefsIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.posting_disabled)
    sketch = db.execute(select(Sketch).where(Sketch.id == sketch_id)).scalar_one_or_none()
    if not sketch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Интересующий вас объект был удалён',
        )
    if str(sketch.author_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    db.execute(SketchStyle.__table__.delete().where(SketchStyle.sketch_id == sketch_id))
    for style_id in payload.ids:
        db.add(SketchStyle(sketch_id=sketch_id, style_id=style_id))
    db.commit()
    return payload.ids


@router.get('/{sketch_id}/tags', response_model=list[str])
def get_sketch_tags(sketch_id: str, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(SketchTag.tag_id).where(SketchTag.sketch_id == sketch_id)).scalars().all()
    return [str(r) for r in rows]


@router.put('/{sketch_id}/tags', response_model=list[str])
def set_sketch_tags(
    sketch_id: str,
    payload: SketchRefsIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.posting_disabled)
    sketch = db.execute(select(Sketch).where(Sketch.id == sketch_id)).scalar_one_or_none()
    if not sketch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Интересующий вас объект был удалён',
        )
    if str(sketch.author_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    db.execute(SketchTag.__table__.delete().where(SketchTag.sketch_id == sketch_id))
    for tag_id in payload.ids:
        db.add(SketchTag(sketch_id=sketch_id, tag_id=tag_id))
    db.commit()
    return payload.ids
