from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.sketches import FeedPreferredStyle, FeedPreferredTag, SketchStyle, SketchTag

MIN_WEIGHT = -10
MAX_WEIGHT = 10


def _clamp(value: int) -> int:
    return max(MIN_WEIGHT, min(MAX_WEIGHT, value))


def _get_style_row(db: Session, user_id: str, style_id: str) -> FeedPreferredStyle | None:
    return db.execute(
        select(FeedPreferredStyle).where(
            FeedPreferredStyle.user_id == user_id,
            FeedPreferredStyle.style_id == style_id,
        )
    ).scalar_one_or_none()


def _get_tag_row(db: Session, user_id: str, tag_id: str) -> FeedPreferredTag | None:
    return db.execute(
        select(FeedPreferredTag).where(
            FeedPreferredTag.user_id == user_id,
            FeedPreferredTag.tag_id == tag_id,
        )
    ).scalar_one_or_none()


def _ensure_style_row(db: Session, user_id: str, style_id: str) -> FeedPreferredStyle:
    row = _get_style_row(db, user_id, style_id)
    if row:
        return row
    row = FeedPreferredStyle(user_id=user_id, style_id=style_id, weight=0)
    db.add(row)
    return row


def _ensure_tag_row(db: Session, user_id: str, tag_id: str) -> FeedPreferredTag:
    row = _get_tag_row(db, user_id, tag_id)
    if row:
        return row
    row = FeedPreferredTag(user_id=user_id, tag_id=tag_id, weight=0)
    db.add(row)
    return row


def _decay_other_rows(
    db: Session,
    user_id: str,
    *,
    excluded_style_ids: set[str],
    excluded_tag_ids: set[str],
) -> None:
    style_rows = db.execute(
        select(FeedPreferredStyle).where(FeedPreferredStyle.user_id == user_id)
    ).scalars().all()
    tag_rows = db.execute(
        select(FeedPreferredTag).where(FeedPreferredTag.user_id == user_id)
    ).scalars().all()

    for row in style_rows:
        if str(row.style_id) in excluded_style_ids:
            continue
        current = int(row.weight or 0)
        if current <= 0:
            continue
        row.weight = _clamp(current - 1)
    for row in tag_rows:
        if str(row.tag_id) in excluded_tag_ids:
            continue
        current = int(row.weight or 0)
        if current <= 0:
            continue
        row.weight = _clamp(current - 1)


def _apply_weight_change(
    db: Session,
    *,
    user_id: str,
    style_ids: Iterable[str] = (),
    tag_ids: Iterable[str] = (),
    delta: int,
) -> None:
    style_ids = [str(style_id) for style_id in style_ids]
    tag_ids = [str(tag_id) for tag_id in tag_ids]
    if not style_ids and not tag_ids:
        return

    should_decay_others = False

    for style_id in style_ids:
        row = _ensure_style_row(db, user_id, style_id)
        current = int(row.weight or 0)
        if delta > 0:
            next_value = _clamp(current + delta)
            row.weight = next_value
            if next_value >= MAX_WEIGHT:
                should_decay_others = True
        else:
            row.weight = _clamp(current + delta)

    for tag_id in tag_ids:
        row = _ensure_tag_row(db, user_id, tag_id)
        current = int(row.weight or 0)
        if delta > 0:
            next_value = _clamp(current + delta)
            row.weight = next_value
            if next_value >= MAX_WEIGHT:
                should_decay_others = True
        else:
            row.weight = _clamp(current + delta)

    if should_decay_others:
        _decay_other_rows(
            db,
            user_id,
            excluded_style_ids=set(style_ids),
            excluded_tag_ids=set(tag_ids),
        )


def set_preference_weight(
    db: Session,
    *,
    user_id: str,
    kind: str,
    item_id: str,
    weight: int,
) -> None:
    weight = _clamp(weight)
    if kind == 'style':
        row = _get_style_row(db, user_id, item_id)
        if weight == 0:
            if row:
                db.delete(row)
        elif row:
            row.weight = weight
        else:
            db.add(FeedPreferredStyle(user_id=user_id, style_id=item_id, weight=weight))
    elif kind == 'tag':
        row = _get_tag_row(db, user_id, item_id)
        if weight == 0:
            if row:
                db.delete(row)
        elif row:
            row.weight = weight
        else:
            db.add(FeedPreferredTag(user_id=user_id, tag_id=item_id, weight=weight))


def bulk_set_preferences(
    db: Session,
    *,
    user_id: str,
    style_weights: dict[str, int],
    tag_weights: dict[str, int],
) -> None:
    db.execute(delete(FeedPreferredStyle).where(FeedPreferredStyle.user_id == user_id))
    db.execute(delete(FeedPreferredTag).where(FeedPreferredTag.user_id == user_id))
    for style_id, weight in style_weights.items():
        if weight != 0:
            db.add(FeedPreferredStyle(user_id=user_id, style_id=style_id, weight=_clamp(weight)))
    for tag_id, weight in tag_weights.items():
        if weight != 0:
            db.add(FeedPreferredTag(user_id=user_id, tag_id=tag_id, weight=_clamp(weight)))


def get_preference_weights(db: Session, user_id: str) -> tuple[dict[str, int], dict[str, int]]:
    style_rows = db.execute(
        select(FeedPreferredStyle.style_id, FeedPreferredStyle.weight).where(FeedPreferredStyle.user_id == user_id)
    ).all()
    tag_rows = db.execute(
        select(FeedPreferredTag.tag_id, FeedPreferredTag.weight).where(FeedPreferredTag.user_id == user_id)
    ).all()
    styles = {str(style_id): int(weight or 0) for style_id, weight in style_rows}
    tags = {str(tag_id): int(weight or 0) for tag_id, weight in tag_rows}
    return styles, tags


def update_preferences_for_sketch(db: Session, user_id: str, sketch_id: str, delta: int) -> None:
    style_ids = db.execute(
        select(SketchStyle.style_id).where(SketchStyle.sketch_id == sketch_id)
    ).scalars().all()
    tag_ids = db.execute(
        select(SketchTag.tag_id).where(SketchTag.sketch_id == sketch_id)
    ).scalars().all()
    if delta == 0:
        return
    _apply_weight_change(
        db,
        user_id=user_id,
        style_ids=[str(style_id) for style_id in style_ids],
        tag_ids=[str(tag_id) for tag_id in tag_ids],
        delta=delta,
    )


def apply_preference_action(db: Session, user_id: str, sketch_id: str, action: str) -> None:
    delta = {
        'register': 1,
        'like': 1,
        'like_removed': -1,
        'save': 2,
        'comment': 1,
        'request': 3,
    }.get(action, 0)
    update_preferences_for_sketch(db, user_id, sketch_id, delta)
