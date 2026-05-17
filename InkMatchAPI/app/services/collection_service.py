from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.enums import CollectionType
from app.models.sketches import Collection, CollectionItem, Sketch, SketchMedia
from app.services.media_service import resolve_media_url


MASTER_COLLECTION_TYPES = {'portfolio', 'process', 'achievments', 'find_us', 'materials'}


def _ensure_system_custom_collection(
    db: Session,
    owner_id: str,
    *,
    title: str,
    description: str,
    is_private: bool,
):
    existing = db.execute(
        select(Collection).where(
            Collection.owner_id == owner_id,
            Collection.is_system.is_(True),
            Collection.collection_type == CollectionType.custom,
            Collection.title == title,
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    row = Collection(
        owner_id=owner_id,
        collection_type=CollectionType.custom,
        title=title,
        description=description,
        is_system=True,
        is_private=is_private,
    )
    db.add(row)
    db.flush()
    return row


def _collection_items_payload(db: Session, collection_id):
    stmt = (
        select(
            CollectionItem.sketch_id,
            SketchMedia.url,
            CollectionItem.work_duration_houres,
            CollectionItem.work_price,
            CollectionItem.currency,
            CollectionItem.note,
        )
        .outerjoin(
            SketchMedia,
            and_(
                SketchMedia.sketch_id == CollectionItem.sketch_id,
                SketchMedia.sort_order == 0,
            ),
        )
        .where(CollectionItem.collection_id == collection_id)
        .order_by(CollectionItem.sort_order.asc())
    )
    rows = db.execute(stmt).all()
    return [
        {
            'sketch_id': str(sketch_id),
            'media_url': resolve_media_url(url) if url else None,
            'work_duration_houres': work_duration_houres,
            'work_price': work_price,
            'currency': currency,
            'note': note,
        }
        for sketch_id, url, work_duration_houres, work_price, currency, note in rows
    ]


def list_collections(db: Session, owner_id: str, section: str | None = None):
    stmt = select(Collection).where(Collection.owner_id == owner_id)
    if section == 'master':
        stmt = stmt.where(Collection.collection_type.in_(MASTER_COLLECTION_TYPES))
    rows = db.execute(stmt.order_by(Collection.created_at.desc())).scalars().all()

    items = []
    for col in rows:
        count_stmt = select(func.count()).select_from(CollectionItem).where(CollectionItem.collection_id == col.id)
        item_count = db.execute(count_stmt).scalar_one() or 0

        preview_stmt = (
            select(SketchMedia.url)
            .join(CollectionItem, CollectionItem.sketch_id == SketchMedia.sketch_id)
            .where(CollectionItem.collection_id == col.id)
            .order_by(CollectionItem.sort_order.asc(), SketchMedia.sort_order.asc())
            .limit(1)
        )
        preview_url = db.execute(preview_stmt).scalar_one_or_none()

        items.append(
            {
                'id': str(col.id),
                'owner_id': str(col.owner_id),
                'title': col.title,
                'description': col.description,
                'collection_type': col.collection_type.value,
                'is_system': bool(col.is_system),
                'is_private': bool(col.is_private),
                'preview_url': resolve_media_url(preview_url) if preview_url else None,
                'item_count': int(item_count),
            }
        )
    return items


def get_collection_by_id(db: Session, collection_id: str):
    collection = db.execute(select(Collection).where(Collection.id == collection_id)).scalar_one_or_none()
    if not collection:
        return None

    media_stmt = (
        select(SketchMedia.url)
        .join(CollectionItem, CollectionItem.sketch_id == SketchMedia.sketch_id)
        .where(CollectionItem.collection_id == collection.id)
        .order_by(CollectionItem.sort_order.asc(), SketchMedia.sort_order.asc())
    )
    media_urls = list(db.execute(media_stmt).scalars().all())

    return {
        'id': str(collection.id),
        'owner_id': str(collection.owner_id),
        'title': collection.title,
        'description': collection.description,
        'collection_type': collection.collection_type.value,
        'is_system': bool(collection.is_system),
        'is_private': bool(collection.is_private),
        'media_urls': [resolve_media_url(url) if url else None for url in media_urls],
        'items': _collection_items_payload(db, collection.id),
    }


def create_collection(
    db: Session,
    owner_id: str,
    title: str,
    description: str | None,
    collection_type: str,
    is_private: bool,
):
    clean_title = (title or '').strip()
    if not clean_title:
        return None

    try:
        ctype = CollectionType(collection_type)
    except ValueError:
        ctype = CollectionType.custom

    collection = Collection(
        owner_id=owner_id,
        title=clean_title,
        description=(description or '').strip() or None,
        collection_type=ctype,
        is_private=is_private,
        is_system=False,
    )
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return collection


def delete_collection(db: Session, collection_id: str, owner_id: str):
    collection = db.execute(select(Collection).where(Collection.id == collection_id)).scalar_one_or_none()
    if not collection:
        return 'not_found'
    if str(collection.owner_id) != str(owner_id):
        return 'forbidden'
    if collection.is_system:
        return 'system_locked'

    db.execute(
        CollectionItem.__table__.delete().where(CollectionItem.collection_id == collection.id)
    )
    db.delete(collection)
    db.commit()
    return None


def update_collection(
    db: Session,
    collection_id: str,
    owner_id: str,
    title: str | None,
    description: str | None,
    is_private: bool | None,
):
    collection = db.execute(select(Collection).where(Collection.id == collection_id)).scalar_one_or_none()
    if not collection:
        return None, 'not_found'

    if str(collection.owner_id) != str(owner_id):
        return None, 'forbidden'

    if title is not None and collection.is_system:
        return None, 'title_locked'

    if title is not None:
        clean_title = title.strip()
        if not clean_title:
            return None, 'empty_title'
        collection.title = clean_title
    if description is not None:
        collection.description = (description or '').strip() or None
    if is_private is not None:
        collection.is_private = is_private

    db.commit()
    db.refresh(collection)
    return collection, None


def add_collection_item(
    db: Session,
    collection_id: str,
    owner_id: str,
    sketch_id: str,
    sort_order: int | None,
    work_duration_houres: int | None = None,
    work_price: int | None = None,
    currency: str | None = None,
    note: str | None = None,
):
    collection = db.execute(select(Collection).where(Collection.id == collection_id)).scalar_one_or_none()
    if not collection:
        return 'not_found'
    if str(collection.owner_id) != str(owner_id):
        return 'forbidden'

    sketch = db.execute(select(Sketch).where(Sketch.id == sketch_id)).scalar_one_or_none()
    if not sketch:
        return 'sketch_not_found'

    existing = db.execute(
        select(CollectionItem).where(
            CollectionItem.collection_id == collection_id,
            CollectionItem.sketch_id == sketch_id,
        )
    ).scalar_one_or_none()
    if existing:
        existing.work_duration_houres = work_duration_houres
        existing.work_price = work_price
        existing.currency = (currency or '').strip().upper()[:3] or None
        existing.note = (note or '').strip() or None
        db.commit()
        return False

    if sort_order is None:
        max_order = db.execute(
            select(func.coalesce(func.max(CollectionItem.sort_order), 0)).where(
                CollectionItem.collection_id == collection_id
            )
        ).scalar_one()
        sort_order = int(max_order) + 1

    db.add(
        CollectionItem(
            collection_id=collection_id,
            sketch_id=sketch_id,
            sort_order=sort_order,
            work_duration_houres=work_duration_houres,
            work_price=work_price,
            currency=(currency or '').strip().upper()[:3] or None,
            note=(note or '').strip() or None,
        )
    )
    db.commit()
    return True


def remove_collection_item(db: Session, collection_id: str, sketch_id: str, owner_id: str):
    collection = db.execute(select(Collection).where(Collection.id == collection_id)).scalar_one_or_none()
    if not collection:
        return 'not_found'
    if str(collection.owner_id) != str(owner_id):
        return 'forbidden'

    row = db.execute(
        select(CollectionItem).where(
            CollectionItem.collection_id == collection_id,
            CollectionItem.sketch_id == sketch_id,
        )
    ).scalar_one_or_none()
    if not row:
        return 'item_not_found'

    db.delete(row)
    db.commit()
    return None


def update_collection_item_metadata(
    db: Session,
    collection_id: str,
    sketch_id: str,
    owner_id: str,
    *,
    work_duration_houres: int | None,
    work_price: int | None,
    currency: str | None,
    note: str | None,
):
    collection = db.execute(select(Collection).where(Collection.id == collection_id)).scalar_one_or_none()
    if not collection:
        return 'not_found'
    if str(collection.owner_id) != str(owner_id):
        return 'forbidden'

    row = db.execute(
        select(CollectionItem).where(
            CollectionItem.collection_id == collection_id,
            CollectionItem.sketch_id == sketch_id,
        )
    ).scalar_one_or_none()
    if not row:
        return 'item_not_found'

    row.work_duration_houres = work_duration_houres
    row.work_price = work_price
    row.currency = (currency or '').strip().upper()[:3] or None
    row.note = (note or '').strip() or None
    db.commit()
    return None


def ensure_likes_collection(db: Session, owner_id: str):
    existing = db.execute(
        select(Collection).where(
            Collection.owner_id == owner_id,
            Collection.collection_type == CollectionType.likes,
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    collection = Collection(
        owner_id=owner_id,
        collection_type=CollectionType.likes,
        title='Избранное',
        description='Сохраненные понравившиеся посты',
        is_system=True,
        is_private=False,
    )
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return collection




def ensure_my_posts_collection(db: Session, owner_id: str):
    return _ensure_system_custom_collection(
        db,
        owner_id,
        title='Мои посты',
        description='Посты и эскизы, созданные пользователем',
        is_private=False,
    )


def ensure_inkmatch_collection(db: Session, owner_id: str):
    return _ensure_system_custom_collection(
        db,
        owner_id,
        title='InkMatch',
        description='Работы, по которым пользователь создавал заявки InkMatch',
        is_private=True,
    )


def save_collection_to_user(db: Session, source_collection_id: str, target_owner_id: str):
    source = db.execute(select(Collection).where(Collection.id == source_collection_id)).scalar_one_or_none()
    if not source:
        return None, 'not_found'

    if source.is_private and str(source.owner_id) != str(target_owner_id):
        return None, 'forbidden'

    clone = Collection(
        owner_id=target_owner_id,
        collection_type=CollectionType.custom,
        title=f"Saved: {source.title}",
        description=source.description,
        is_system=False,
        is_private=False,
    )
    db.add(clone)
    db.flush()

    items = db.execute(
        select(CollectionItem).where(CollectionItem.collection_id == source.id)
    ).scalars().all()
    for item in items:
        db.add(
            CollectionItem(
                collection_id=clone.id,
                sketch_id=item.sketch_id,
                sort_order=item.sort_order,
                work_duration_houres=item.work_duration_houres,
                work_price=item.work_price,
                currency=item.currency,
                note=item.note,
            )
        )

    db.commit()
    db.refresh(clone)
    return clone, None
