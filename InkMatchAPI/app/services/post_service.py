from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy import desc

from app.models.enums import NotificationType
from sqlalchemy.orm import Session

from app.models.profiles import Profile
from app.models.sketches import (
    CollectionItem,
    Sketch,
    SketchComment,
    SketchLike,
    SketchMedia,
    Style,
    Tag,
    SketchStyle,
    SketchTag,
)
from app.services.collection_service import add_collection_item, ensure_likes_collection, remove_collection_item
from app.services.notification_service import create_notification, user_nickname
from app.services.media_service import resolve_media_url
from app.services.preference_weight_service import apply_preference_action, get_preference_weights


def _first_media_url(db: Session, sketch_id: str):
    raw_url = db.execute(
        select(SketchMedia.url)
        .where(SketchMedia.sketch_id == sketch_id)
        .order_by(SketchMedia.sort_order.asc())
        .limit(1)
    ).scalar_one_or_none()
    return resolve_media_url(raw_url) if raw_url else None


def _preference_score_average(
    style_weights: dict[str, int],
    tag_weights: dict[str, int],
    sketch_style_ids: list[str],
    sketch_tag_ids: list[str],
) -> float:
    values: list[int] = []
    for style_id in sketch_style_ids:
        weight = int(style_weights.get(str(style_id), 0) or 0)
        if weight != 0:
            values.append(weight)
    for tag_id in sketch_tag_ids:
        weight = int(tag_weights.get(str(tag_id), 0) or 0)
        if weight != 0:
            values.append(weight)
    if not values:
        return 0.0
    return sum(values) / len(values)


def get_feed_posts(
    db: Session,
    limit: int = 20,
    offset: int = 0,
    style_ids: list[str] | None = None,
    tag_ids: list[str] | None = None,
    content_types: list[str] | None = None,
    min_likes: int | None = None,
    q: str | None = None,
    sort: str = 'newest',
    current_user_id: str | None = None,
):
    stmt = (
        select(Sketch, Profile.nickname)
        .join(Profile, Profile.user_id == Sketch.author_id)
        .where(Sketch.feed_visibility == 'public')
    )

    if style_ids:
        stmt = stmt.where(
            Sketch.id.in_(
                select(SketchStyle.sketch_id).where(SketchStyle.style_id.in_(style_ids))
            )
        )

    if tag_ids:
        stmt = stmt.where(
            Sketch.id.in_(
                select(SketchTag.sketch_id).where(SketchTag.tag_id.in_(tag_ids))
            )
        )

    if content_types:
        stmt = stmt.where(Sketch.content_type.in_(content_types))

    if q:
        term = f"%{q.strip()}%"
        if term != '%%':
            stmt = stmt.where(
                or_(
                    Sketch.title.ilike(term),
                    Sketch.description.ilike(term),
                    Profile.nickname.ilike(term),
                )
            )

    sort = (sort or 'newest').strip().lower()
    recent_cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    recent_likes = (
        select(
            SketchLike.sketch_id.label('sketch_id'),
            func.count().label('recent_like_count'),
        )
        .where(SketchLike.created_at >= recent_cutoff)
        .group_by(SketchLike.sketch_id)
        .subquery()
    )
    if sort in {'popular', 'trending'}:
        stmt = stmt.outerjoin(recent_likes, recent_likes.c.sketch_id == Sketch.id)
    if min_likes is not None:
        stmt = stmt.where(Sketch.like_amount >= int(min_likes))

    rows = db.execute(stmt.order_by(Sketch.created_at.desc()).limit(400)).all()

    style_weights, tag_weights = ({}, {})
    if current_user_id:
        style_weights, tag_weights = get_preference_weights(db, current_user_id)

    recent_like_counts = {}
    if sort == 'trending':
        recent_like_counts = {
            str(sketch_id): int(count or 0)
            for sketch_id, count in db.execute(
                select(recent_likes.c.sketch_id, recent_likes.c.recent_like_count)
            ).all()
        }

    scored = []
    for sketch, nickname in rows:
        image_url = _first_media_url(db, str(sketch.id))
        comment_count = db.execute(
            select(func.count()).select_from(SketchComment).where(
                SketchComment.sketch_id == sketch.id,
                SketchComment.is_deleted.is_(False),
            )
        ).scalar_one() or 0
        sketch_style_ids = db.execute(
            select(SketchStyle.style_id).where(SketchStyle.sketch_id == sketch.id)
        ).scalars().all()
        sketch_tag_ids = db.execute(
            select(SketchTag.tag_id).where(SketchTag.sketch_id == sketch.id)
        ).scalars().all()
        preference_score = _preference_score_average(
            style_weights,
            tag_weights,
            [str(style_id) for style_id in sketch_style_ids],
            [str(tag_id) for tag_id in sketch_tag_ids],
        )
        if sort == 'popular':
            secondary = int(sketch.like_amount or 0)
        elif sort == 'trending':
            secondary = recent_like_counts.get(str(sketch.id), 0)
        elif sort == 'preferred':
            secondary = preference_score
        else:
            secondary = int(sketch.like_amount or 0)
        jitter = (int(str(sketch.id).replace('-', '')[:8], 16) ^ int(sketch.like_amount or 0)) % 997 / 997.0
        scored.append(
            (
                preference_score,
                secondary,
                sketch.created_at,
                jitter,
                sketch,
                nickname,
                image_url,
                comment_count,
            )
        )

    scored.sort(key=lambda row: (row[0], row[1], row[2], row[3]), reverse=True)
    page = scored[offset:offset + limit]

    result = []
    for _, __, ___, ____, sketch, nickname, image_url, comment_count in page:
        result.append(
            {
                'id': str(sketch.id),
                'author_id': str(sketch.author_id),
                'author_nickname': nickname,
                'image_url': resolve_media_url(image_url) if image_url else None,
                'title': sketch.title,
                'like_amount': int(sketch.like_amount or 0),
                'comment_count': int(comment_count),
            }
        )
    return result


def _feed_item(db: Session, sketch: Sketch, nickname: str):
    image_url = _first_media_url(db, str(sketch.id))
    comment_count = db.execute(
        select(func.count()).select_from(SketchComment).where(
            SketchComment.sketch_id == sketch.id,
            SketchComment.is_deleted.is_(False),
        )
    ).scalar_one() or 0
    return {
        'id': str(sketch.id),
        'author_id': str(sketch.author_id),
        'author_nickname': nickname,
        'image_url': resolve_media_url(image_url) if image_url else None,
        'title': sketch.title,
        'like_amount': int(sketch.like_amount or 0),
        'comment_count': int(comment_count),
    }


def _hex_hamming(a: str | None, b: str | None) -> int | None:
    if not a or not b:
        return None
    try:
        return (int(a, 16) ^ int(b, 16)).bit_count()
    except ValueError:
        return None


def get_similar_posts(db: Session, sketch_id: str, limit: int = 20, offset: int = 0):
    source = db.execute(select(Sketch).where(Sketch.id == sketch_id)).scalar_one_or_none()
    if not source:
        return None

    source_style_ids = set(
        db.execute(select(SketchStyle.style_id).where(SketchStyle.sketch_id == sketch_id)).scalars().all()
    )
    source_tag_ids = set(
        db.execute(select(SketchTag.tag_id).where(SketchTag.sketch_id == sketch_id)).scalars().all()
    )
    source_phash = db.execute(
        select(SketchMedia.phash)
        .where(SketchMedia.sketch_id == sketch_id, SketchMedia.phash.is_not(None))
        .order_by(SketchMedia.sort_order.asc())
        .limit(1)
    ).scalar_one_or_none()

    rows = db.execute(
        select(Sketch, Profile.nickname)
        .join(Profile, Profile.user_id == Sketch.author_id)
        .where(
            Sketch.feed_visibility == 'public',
            Sketch.id != sketch_id,
        )
        .order_by(desc(Sketch.like_amount), desc(Sketch.created_at))
        .limit(200)
    ).all()

    scored = []
    for sketch, nickname in rows:
        style_ids = set(
            db.execute(select(SketchStyle.style_id).where(SketchStyle.sketch_id == sketch.id)).scalars().all()
        )
        tag_ids = set(
            db.execute(select(SketchTag.tag_id).where(SketchTag.sketch_id == sketch.id)).scalars().all()
        )
        phash = db.execute(
            select(SketchMedia.phash)
            .where(SketchMedia.sketch_id == sketch.id, SketchMedia.phash.is_not(None))
            .order_by(SketchMedia.sort_order.asc())
            .limit(1)
        ).scalar_one_or_none()
        visual_distance = _hex_hamming(source_phash, phash)
        visual_score = 0 if visual_distance is None else max(0, 64 - visual_distance)
        score = (
            len(source_style_ids & style_ids) * 40
            + len(source_tag_ids & tag_ids) * 20
            + visual_score
            + min(int(sketch.like_amount or 0), 50) * 0.2
        )
        scored.append((score, sketch.created_at, sketch, nickname))

    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    page = scored[offset:offset + limit]
    return [_feed_item(db, sketch, nickname) for _, __, sketch, nickname in page]


def get_post_detail(db: Session, sketch_id: str, current_user_id: str):
    row = db.execute(
        select(Sketch, Profile.nickname)
        .join(Profile, Profile.user_id == Sketch.author_id)
        .where(Sketch.id == sketch_id)
    ).first()
    if not row:
        return None

    sketch, nickname = row
    media_urls = list(
        db.execute(
            select(SketchMedia.url)
            .where(SketchMedia.sketch_id == sketch.id)
            .order_by(SketchMedia.sort_order.asc())
        ).scalars().all()
    )

    comment_count = db.execute(
        select(func.count()).select_from(SketchComment).where(
            SketchComment.sketch_id == sketch.id,
            SketchComment.is_deleted.is_(False),
        )
    ).scalar_one() or 0

    is_liked = db.execute(
        select(SketchLike).where(
            SketchLike.user_id == current_user_id,
            SketchLike.sketch_id == sketch.id,
        )
    ).scalar_one_or_none() is not None

    likes_collection = ensure_likes_collection(db, current_user_id)
    is_saved = db.execute(
        select(CollectionItem).where(
            CollectionItem.collection_id == likes_collection.id,
            CollectionItem.sketch_id == sketch.id,
        )
    ).scalar_one_or_none() is not None

    return {
        'id': str(sketch.id),
        'author_id': str(sketch.author_id),
        'author_nickname': nickname,
        'title': sketch.title,
        'description': sketch.description,
        'styles': [
            {'id': str(row.id), 'name': row.name}
            for row in db.execute(
                select(Style)
                .join(SketchStyle, SketchStyle.style_id == Style.id)
                .where(SketchStyle.sketch_id == sketch.id)
                .order_by(Style.name.asc())
            ).scalars().all()
        ],
        'tags': [
            {'id': str(row.id), 'name': row.name}
            for row in db.execute(
                select(Tag)
                .join(SketchTag, SketchTag.tag_id == Tag.id)
                .where(SketchTag.sketch_id == sketch.id)
                .order_by(Tag.name.asc())
            ).scalars().all()
        ],
        'media_urls': [resolve_media_url(url) if url else None for url in media_urls],
        'like_amount': int(sketch.like_amount or 0),
        'comment_count': int(comment_count),
        'is_liked': is_liked,
        'is_saved': is_saved,
    }


def toggle_post_like(db: Session, sketch_id: str, current_user_id: str):
    sketch = db.execute(select(Sketch).where(Sketch.id == sketch_id)).scalar_one_or_none()
    if not sketch:
        return None

    like_row = db.execute(
        select(SketchLike).where(
            SketchLike.user_id == current_user_id,
            SketchLike.sketch_id == sketch_id,
        )
    ).scalar_one_or_none()

    likes_collection = ensure_likes_collection(db, current_user_id)

    if like_row:
        db.delete(like_row)
        sketch.like_amount = max(0, int(sketch.like_amount or 0) - 1)
        item = db.execute(
            select(CollectionItem).where(
                CollectionItem.collection_id == likes_collection.id,
                CollectionItem.sketch_id == sketch_id,
            )
        ).scalar_one_or_none()
        if item:
            db.delete(item)
        is_liked = False
        apply_preference_action(db, current_user_id, sketch_id, 'like_removed')
    else:
        db.add(SketchLike(user_id=current_user_id, sketch_id=sketch_id))
        sketch.like_amount = int(sketch.like_amount or 0) + 1
        item = db.execute(
            select(CollectionItem).where(
                CollectionItem.collection_id == likes_collection.id,
                CollectionItem.sketch_id == sketch_id,
            )
        ).scalar_one_or_none()
        if not item:
            db.add(
                CollectionItem(
                    collection_id=likes_collection.id,
                    sketch_id=sketch_id,
                    sort_order=0,
                )
            )
        is_liked = True
        apply_preference_action(db, current_user_id, sketch_id, 'like')

    db.commit()

    if is_liked and str(sketch.author_id) != str(current_user_id):
        actor = user_nickname(db, current_user_id)
        create_notification(
            db,
            user_id=str(sketch.author_id),
            type_=NotificationType.system,
            title='Новый лайк',
            body=f'{actor} оценил(а) ваш пост',
            deep_link=f'/post/{sketch_id}',
            image_url=_first_media_url(db, sketch_id),
            links=[('sketch', sketch_id)],
        )
        db.commit()

    return {'is_liked': is_liked, 'like_amount': int(sketch.like_amount or 0)}


def list_post_comments(db: Session, sketch_id: str):
    rows = db.execute(
        select(SketchComment, Profile.nickname)
        .join(Profile, Profile.user_id == SketchComment.author_user_id)
        .where(
            SketchComment.sketch_id == sketch_id,
            SketchComment.is_deleted.is_(False),
        )
        .order_by(SketchComment.created_at.asc())
    ).all()

    return [
        {
            'id': str(comment.id),
            'author_user_id': str(comment.author_user_id),
            'author_nickname': nickname,
            'parent_comment_id': str(comment.parent_comment_id) if comment.parent_comment_id else None,
            'body': comment.body,
            'created_at': comment.created_at.astimezone(timezone.utc).isoformat(),
        }
        for comment, nickname in rows
    ]


def create_post_comment(db: Session, sketch_id: str, author_user_id: str, body: str, parent_comment_id: str | None = None):
    sketch = db.execute(select(Sketch).where(Sketch.id == sketch_id)).scalar_one_or_none()
    if not sketch:
        return None
    parent_comment = None
    if parent_comment_id:
        parent_comment = db.execute(
            select(SketchComment).where(
                SketchComment.id == parent_comment_id,
                SketchComment.sketch_id == sketch.id,
                SketchComment.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        if not parent_comment:
            return 'parent_not_found'

    comment = SketchComment(
        sketch_id=sketch_id,
        author_user_id=author_user_id,
        parent_comment_id=parent_comment.id if parent_comment else None,
        body=body,
        is_deleted=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(comment)
    apply_preference_action(db, author_user_id, sketch_id, 'comment')
    db.commit()
    db.refresh(comment)

    nickname = db.execute(select(Profile.nickname).where(Profile.user_id == author_user_id)).scalar_one_or_none()

    if str(sketch.author_id) != str(author_user_id):
        actor = nickname or user_nickname(db, author_user_id)
        create_notification(
            db,
            user_id=str(sketch.author_id),
            type_=NotificationType.system,
            title='Новый комментарий',
            body=f'{actor} оставил(а) комментарий к вашему посту',
            deep_link=f'/post/{sketch_id}',
            image_url=_first_media_url(db, sketch_id),
            links=[('sketch', sketch_id), ('comment', str(comment.id))],
        )
        db.commit()

    if parent_comment and str(parent_comment.author_user_id) != str(author_user_id):
        actor = nickname or user_nickname(db, author_user_id)
        create_notification(
            db,
            user_id=str(parent_comment.author_user_id),
            type_=NotificationType.system,
            title='Ответ на комментарий',
            body=f'{actor} ответил(а) на ваш комментарий',
            deep_link=f'/post/{sketch_id}',
            image_url=_first_media_url(db, sketch_id),
            links=[('sketch', sketch_id), ('comment', str(comment.id)), ('parent_comment', str(parent_comment.id))],
        )
        db.commit()

    return {
        'id': str(comment.id),
        'author_user_id': str(comment.author_user_id),
        'author_nickname': nickname or 'user',
        'parent_comment_id': str(comment.parent_comment_id) if comment.parent_comment_id else None,
        'body': comment.body,
        'created_at': comment.created_at.astimezone(timezone.utc).isoformat(),
    }


def toggle_post_save(db: Session, sketch_id: str, current_user_id: str):
    sketch = db.execute(select(Sketch).where(Sketch.id == sketch_id)).scalar_one_or_none()
    if not sketch:
        return None

    likes_collection = ensure_likes_collection(db, current_user_id)

    existing = db.execute(
        select(CollectionItem).where(
            CollectionItem.collection_id == likes_collection.id,
            CollectionItem.sketch_id == sketch_id,
        )
    ).scalar_one_or_none()

    if existing:
        remove_collection_item(db, str(likes_collection.id), sketch_id, current_user_id)
        return {'is_saved': False}

    add_collection_item(db, str(likes_collection.id), current_user_id, sketch_id, None)
    apply_preference_action(db, current_user_id, sketch_id, 'save')

    if str(sketch.author_id) != str(current_user_id):
        actor = user_nickname(db, current_user_id)
        create_notification(
            db,
            user_id=str(sketch.author_id),
            type_=NotificationType.system,
            title='Пост сохранен',
            body=f'{actor} сохранил(а) ваш пост',
            deep_link=f'/post/{sketch_id}',
            image_url=_first_media_url(db, sketch_id),
            links=[('sketch', sketch_id)],
        )
        db.commit()

    return {'is_saved': True}


def delete_post_comment(db: Session, comment_id: str, current_user_id: str, *, allow_moderator: bool = False) -> str | None:
    comment = db.execute(select(SketchComment).where(SketchComment.id == comment_id)).scalar_one_or_none()
    if not comment:
        return 'not_found'
    sketch = db.execute(select(Sketch).where(Sketch.id == comment.sketch_id)).scalar_one_or_none()
    if not sketch:
        return 'not_found'
    if (
        str(comment.author_user_id) != str(current_user_id)
        and str(sketch.author_id) != str(current_user_id)
        and not allow_moderator
    ):
        return 'forbidden'
    comment.is_deleted = True
    comment.updated_at = datetime.now(timezone.utc)
    db.commit()
    return None
