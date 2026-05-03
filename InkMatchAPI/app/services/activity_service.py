from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.inkmatch import Inkmatch, InkmatchRequest, MasterInkmatchOffer
from app.models.moderation import AuditEvent, AuditEventTarget
from app.models.sketches import (
    Collection,
    CollectionItem,
    Sketch,
    SketchComment,
    SketchLike,
    SketchStyle,
    SketchTag,
    Style,
    Tag,
)


def build_activity_stats(db: Session, user_id: str, role: UserRole, range_days: int) -> dict:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=range_days - 1)
    start_date = start.date()

    style_rows = db.execute(
        select(Style.name, func.count().label('cnt'))
        .select_from(CollectionItem)
        .join(Collection, Collection.id == CollectionItem.collection_id)
        .join(SketchStyle, SketchStyle.sketch_id == CollectionItem.sketch_id)
        .join(Style, Style.id == SketchStyle.style_id)
        .where(
            Collection.owner_id == user_id,
            CollectionItem.added_at >= start,
        )
        .group_by(Style.name)
        .order_by(func.count().desc())
        .limit(8)
    ).all()

    tag_rows = db.execute(
        select(Tag.name, func.count().label('cnt'))
        .select_from(CollectionItem)
        .join(Collection, Collection.id == CollectionItem.collection_id)
        .join(SketchTag, SketchTag.sketch_id == CollectionItem.sketch_id)
        .join(Tag, Tag.id == SketchTag.tag_id)
        .where(
            Collection.owner_id == user_id,
            CollectionItem.added_at >= start,
        )
        .group_by(Tag.name)
        .order_by(func.count().desc())
        .limit(8)
    ).all()

    style_slices = _to_taste_slices(style_rows)
    tag_slices = _to_taste_slices(tag_rows)

    audit_rows = db.execute(
        select(AuditEvent.occurred_at)
        .where(
            AuditEvent.actor_user_id == user_id,
            AuditEvent.occurred_at >= start,
        )
        .order_by(AuditEvent.occurred_at.asc())
    ).scalars().all()

    time_minutes, sessions, active_days = _estimate_time_metrics(audit_rows)

    popularity = _build_popularity(db, user_id, role, start_date, range_days, start)

    saves_count = db.execute(
        select(func.count())
        .select_from(CollectionItem)
        .join(Collection, Collection.id == CollectionItem.collection_id)
        .where(
            Collection.owner_id == user_id,
            CollectionItem.added_at >= start,
        )
    ).scalar_one() or 0

    inkmatch_requests = db.execute(
        select(func.count())
        .select_from(InkmatchRequest)
        .where(
            InkmatchRequest.created_by_user_id == user_id,
            InkmatchRequest.created_at >= start,
        )
    ).scalar_one() or 0

    save_to_inkmatch_rate = (inkmatch_requests / saves_count) if saves_count else 0.0

    streak_days = _current_streak(audit_rows)

    extra: dict[str, float] = {
        'save_to_inkmatch_rate': round(save_to_inkmatch_rate, 4),
        'streak_days': float(streak_days),
    }

    if role == UserRole.master:
        offers_count = db.execute(
            select(func.count())
            .select_from(MasterInkmatchOffer)
            .join(InkmatchRequest, InkmatchRequest.id == MasterInkmatchOffer.request_id)
            .where(
                InkmatchRequest.created_by_user_id == user_id,
                MasterInkmatchOffer.created_at >= start,
            )
        ).scalar_one() or 0

        avg_offer_price = db.execute(
            select(func.avg(MasterInkmatchOffer.offer_price))
            .select_from(MasterInkmatchOffer)
            .join(InkmatchRequest, InkmatchRequest.id == MasterInkmatchOffer.request_id)
            .where(
                InkmatchRequest.created_by_user_id == user_id,
                MasterInkmatchOffer.created_at >= start,
            )
        ).scalar_one()

        matches_count = db.execute(
            select(func.count())
            .select_from(Inkmatch)
            .join(InkmatchRequest, InkmatchRequest.id == Inkmatch.master_request_id)
            .where(
                InkmatchRequest.created_by_user_id == user_id,
                Inkmatch.created_at >= start,
            )
        ).scalar_one() or 0

        extra.update(
            {
                'offers_sent': float(offers_count),
                'avg_offer_price': float(avg_offer_price or 0),
                'matches_count': float(matches_count),
            }
        )
    else:
        collections_created = db.execute(
            select(func.count())
            .select_from(Collection)
            .where(
                Collection.owner_id == user_id,
                Collection.created_at >= start,
                Collection.is_system.is_(False),
            )
        ).scalar_one() or 0

        likes_given = db.execute(
            select(func.count())
            .select_from(SketchLike)
            .where(
                SketchLike.user_id == user_id,
                SketchLike.created_at >= start,
            )
        ).scalar_one() or 0

        comments_written = db.execute(
            select(func.count())
            .select_from(SketchComment)
            .where(
                SketchComment.author_user_id == user_id,
                SketchComment.created_at >= start,
                SketchComment.is_deleted.is_(False),
            )
        ).scalar_one() or 0

        extra.update(
            {
                'collections_created': float(collections_created),
                'likes_given': float(likes_given),
                'comments_written': float(comments_written),
            }
        )

    return {
        'range_days': range_days,
        'role': role.value,
        'taste_styles': style_slices,
        'taste_tags': tag_slices,
        'time_minutes': time_minutes,
        'sessions': sessions,
        'active_days': active_days,
        'popularity': popularity,
        'extra': extra,
    }


def _to_taste_slices(rows: Iterable[tuple[str, int]]) -> list[dict]:
    parsed = [(name, int(cnt)) for name, cnt in rows]
    total = sum(v for _, v in parsed)
    if total <= 0:
        return []
    return [
        {
            'label': name,
            'count': value,
            'share_percent': round((value / total) * 100, 2),
        }
        for name, value in parsed
    ]


def _estimate_time_metrics(events: list[datetime]) -> tuple[int, int, int]:
    if not events:
        return 0, 0, 0

    sessions = 0
    total_minutes = 0
    active_days = len({e.date() for e in events})

    session_start = events[0]
    prev = events[0]
    for cur in events[1:]:
        gap_minutes = (cur - prev).total_seconds() / 60
        if gap_minutes > 30:
            sessions += 1
            total_minutes += _session_minutes(session_start, prev)
            session_start = cur
        prev = cur

    sessions += 1
    total_minutes += _session_minutes(session_start, prev)

    return int(total_minutes), int(sessions), int(active_days)


def _session_minutes(start: datetime, end: datetime) -> int:
    duration = int((end - start).total_seconds() / 60)
    if duration < 2:
        return 2
    if duration > 120:
        return 120
    return duration


def _build_popularity(
    db: Session,
    user_id: str,
    role: UserRole,
    start_date: date,
    range_days: int,
    start_dt: datetime,
) -> list[dict]:
    likes_by_day: dict[date, int] = defaultdict(int)
    comments_by_day: dict[date, int] = defaultdict(int)
    views_by_day: dict[date, int] = defaultdict(int)

    if role == UserRole.master:
        sketch_ids = db.execute(select(Sketch.id).where(Sketch.author_id == user_id)).scalars().all()
        if sketch_ids:
            for day, cnt in db.execute(
                select(func.date(SketchLike.created_at), func.count())
                .select_from(SketchLike)
                .join(Sketch, Sketch.id == SketchLike.sketch_id)
                .where(Sketch.author_id == user_id, SketchLike.created_at >= start_dt)
                .group_by(func.date(SketchLike.created_at))
            ).all():
                likes_by_day[day] = int(cnt)

            for day, cnt in db.execute(
                select(func.date(SketchComment.created_at), func.count())
                .select_from(SketchComment)
                .join(Sketch, Sketch.id == SketchComment.sketch_id)
                .where(
                    Sketch.author_id == user_id,
                    SketchComment.created_at >= start_dt,
                    SketchComment.is_deleted.is_(False),
                )
                .group_by(func.date(SketchComment.created_at))
            ).all():
                comments_by_day[day] = int(cnt)

            for day, cnt in db.execute(
                select(func.date(AuditEvent.occurred_at), func.count())
                .select_from(AuditEventTarget)
                .join(AuditEvent, AuditEvent.id == AuditEventTarget.audit_event_id)
                .where(
                    AuditEvent.occurred_at >= start_dt,
                    AuditEvent.event_type == 'get.get_post',
                    AuditEventTarget.target_type == 'post_id',
                    AuditEventTarget.target_id.in_(sketch_ids),
                )
                .group_by(func.date(AuditEvent.occurred_at))
            ).all():
                views_by_day[day] = int(cnt)
    else:
        for day, cnt in db.execute(
            select(func.date(SketchLike.created_at), func.count())
            .where(
                SketchLike.user_id == user_id,
                SketchLike.created_at >= start_dt,
            )
            .group_by(func.date(SketchLike.created_at))
        ).all():
            likes_by_day[day] = int(cnt)

        for day, cnt in db.execute(
            select(func.date(SketchComment.created_at), func.count())
            .where(
                SketchComment.author_user_id == user_id,
                SketchComment.created_at >= start_dt,
                SketchComment.is_deleted.is_(False),
            )
            .group_by(func.date(SketchComment.created_at))
        ).all():
            comments_by_day[day] = int(cnt)

        for day, cnt in db.execute(
            select(func.date(AuditEvent.occurred_at), func.count())
            .where(
                AuditEvent.actor_user_id == user_id,
                AuditEvent.occurred_at >= start_dt,
                AuditEvent.event_type == 'get.get_post',
            )
            .group_by(func.date(AuditEvent.occurred_at))
        ).all():
            views_by_day[day] = int(cnt)

    result = []
    for i in range(range_days):
        cur_date = start_date + timedelta(days=i)
        result.append(
            {
                'date': cur_date.isoformat(),
                'likes': likes_by_day.get(cur_date, 0),
                'views': views_by_day.get(cur_date, 0),
                'comments': comments_by_day.get(cur_date, 0),
            }
        )

    return result


def _current_streak(events: list[datetime]) -> int:
    if not events:
        return 0

    days = sorted({e.date() for e in events}, reverse=True)
    if not days:
        return 0

    today = datetime.now(timezone.utc).date()
    streak = 0
    expected = today
    idx = 0

    if days and days[0] < today:
        expected = days[0]

    while idx < len(days) and days[idx] == expected:
        streak += 1
        expected = expected - timedelta(days=1)
        idx += 1

    return streak
