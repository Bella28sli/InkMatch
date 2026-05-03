from sqlalchemy import and_, desc, exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.inkmatch import Inkmatch, InkmatchRequest, InkmatchReview, InkmatchReviewAttachment
from app.models.enums import RestrictionType, UserRole, WorkplaceDisplayMode
from app.models.locations import Location, MasterWorkplace, MetroStation
from app.models.profiles import MasterProfile, Profile
from app.models.sketches import Sketch, SketchMedia, SketchStyle, SketchTag
from app.models.user import User
from app.models.user_extras import Subscription, UserRestriction
from app.services.media_service import resolve_media_url


def get_profile(db: Session, user_id: str) -> Profile | None:
    stmt = select(Profile).where(Profile.user_id == user_id)
    return db.execute(stmt).scalar_one_or_none()


def create_profile(db: Session, user_id: str, data):
    profile = Profile(user_id=user_id, **data)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_profile(db: Session, profile: Profile, data):
    for k, v in data.items():
        if v is not None:
            setattr(profile, k, v)
    db.commit()
    db.refresh(profile)
    return profile


def _workplace_public_address(
    workplace: MasterWorkplace | None,
    location: Location | None = None,
    metro_station: MetroStation | None = None,
) -> str | None:
    if not workplace:
        return None
    if workplace.public_text_override:
        address = workplace.public_text_override
    elif workplace.public_display_mode == WorkplaceDisplayMode.metro and metro_station:
        address = ', '.join([p for p in [f'м. {metro_station.name}', metro_station.line_name] if p])
    elif not location:
        address = None
    elif workplace.public_display_mode == WorkplaceDisplayMode.city_only:
        address = ', '.join([p for p in [location.locality, location.region] if p]) or None
    elif workplace.public_display_mode == WorkplaceDisplayMode.full_address:
        address = ', '.join([p for p in [location.address_line, location.locality, location.region] if p]) or None
    else:
        address = ', '.join([p for p in [location.address_line, location.locality] if p]) or None

    return ', '.join([p for p in [workplace.studio_name, address] if p]) or None


def get_profile_full(db: Session, target_user_id: str, current_user_id: str | None = None):
    user = db.execute(select(User).where(User.id == target_user_id)).scalar_one_or_none()
    if not user:
        return None

    if current_user_id is None or str(current_user_id) != str(target_user_id):
        hidden = db.execute(
            select(UserRestriction.id)
            .where(
                UserRestriction.user_id == target_user_id,
                UserRestriction.is_active.is_(True),
                UserRestriction.restriction_type.in_(
                    [RestrictionType.profile_hidden, RestrictionType.full_block]
                ),
            )
            .limit(1)
        ).scalar_one_or_none()
        if hidden:
            return None

    profile = get_profile(db, target_user_id)
    if not profile:
        return None

    followers_count = (
        db.execute(
            select(func.count()).select_from(Subscription).where(Subscription.followed_id == target_user_id)
        ).scalar_one()
        or 0
    )

    review_count_stmt = (
        select(func.count(InkmatchReview.id))
        .select_from(InkmatchReview)
        .join(Inkmatch, Inkmatch.id == InkmatchReview.inkmatch_id)
        .join(InkmatchRequest, InkmatchRequest.id == Inkmatch.client_request_id)
        .where(InkmatchRequest.created_by_user_id == target_user_id)
    )
    client_reviews_count = db.execute(review_count_stmt).scalar_one() or 0

    master_profile = db.execute(
        select(MasterProfile).where(MasterProfile.user_id == target_user_id)
    ).scalar_one_or_none()

    master_address = None
    workplace_row = db.execute(
        select(MasterWorkplace, Location, MetroStation)
        .join(Location, Location.id == MasterWorkplace.location_id)
        .outerjoin(MetroStation, MetroStation.id == MasterWorkplace.public_metro_station_id)
        .where(MasterWorkplace.master_id == target_user_id, MasterWorkplace.is_primary.is_(True))
    ).first()
    if workplace_row:
        workplace, location, metro_station = workplace_row
        master_address = _workplace_public_address(workplace, location, metro_station)

    return {
        'user_id': str(user.id),
        'role': user.role.value,
        'nickname': profile.nickname,
        'avatar_url': resolve_media_url(profile.avatar_url) if profile.avatar_url else None,
        'bio': profile.bio,
        'followers_count': int(followers_count),
        'client_reviews_count': int(client_reviews_count),
        'master_rating': float(master_profile.rating_avg) if master_profile else None,
        'master_completed_works': int(master_profile.completed_sessions_count) if master_profile else None,
        'master_address': master_address,
        'is_verified': bool(master_profile.is_verified) if master_profile else False,
        'verification_skipped': bool(master_profile.verification_skipped) if master_profile else False,
        'is_favorite': bool(master_profile.is_favorite) if master_profile else False,
        'is_owner': current_user_id is not None and str(current_user_id) == str(user.id),
    }


def list_masters_feed(
    db: Session,
    *,
    current_user_id: str,
    search: str | None = None,
    style_ids: list[str] | None = None,
    tag_ids: list[str] | None = None,
    min_rating: float | None = None,
    max_price: int | None = None,
    city_location_id: str | None = None,
    region_location_id: str | None = None,
    center_lat: float | None = None,
    center_lon: float | None = None,
    radius_meters: int | None = None,
    verified_only: bool | None = None,
    favorite_only: bool | None = None,
    sort: str = 'rating_desc',
    limit: int = 20,
    offset: int = 0,
):
    primary_workplace = aliased(MasterWorkplace)
    workplace_location = aliased(Location)

    followers_count_subquery = (
        select(
            Subscription.followed_id.label('followed_id'),
            func.count(Subscription.follower_id).label('followers_count'),
        )
        .group_by(Subscription.followed_id)
        .subquery()
    )

    preview_media_subquery = (
        select(SketchMedia.url)
        .select_from(SketchMedia)
        .join(Sketch, Sketch.id == SketchMedia.sketch_id)
        .where(Sketch.author_id == User.id)
        .order_by(Sketch.created_at.desc(), SketchMedia.sort_order.asc())
        .limit(1)
        .scalar_subquery()
    )

    subscribed_subquery = (
        select(1)
        .select_from(Subscription)
        .where(
            Subscription.follower_id == current_user_id,
            Subscription.followed_id == User.id,
        )
        .limit(1)
    )

    stmt = (
        select(
            User.id.label('user_id'),
            Profile.nickname,
            Profile.avatar_url,
            Profile.bio,
            MasterProfile.description.label('master_description'),
            MasterProfile.rating_avg,
            MasterProfile.completed_sessions_count,
            MasterProfile.price_min,
            MasterProfile.price_max,
            MasterProfile.experience_years,
            MasterProfile.is_verified,
            MasterProfile.is_favorite,
            primary_workplace.studio_name,
            primary_workplace.public_display_mode,
            primary_workplace.public_metro_station_id,
            primary_workplace.public_text_override,
            workplace_location.address_line,
            workplace_location.locality,
            workplace_location.region,
            MetroStation.name.label('metro_station_name'),
            MetroStation.line_name.label('metro_line_name'),
            MetroStation.color_hex.label('metro_color_hex'),
            func.coalesce(followers_count_subquery.c.followers_count, 0).label('followers_count'),
            preview_media_subquery.label('preview_image_url'),
            exists(subscribed_subquery).label('is_subscribed'),
        )
        .join(Profile, Profile.user_id == User.id)
        .join(MasterProfile, MasterProfile.user_id == User.id)
        .outerjoin(
            primary_workplace,
            and_(
                primary_workplace.master_id == User.id,
                primary_workplace.is_primary.is_(True),
            ),
        )
        .outerjoin(workplace_location, workplace_location.id == primary_workplace.location_id)
        .outerjoin(MetroStation, MetroStation.id == primary_workplace.public_metro_station_id)
        .outerjoin(
            followers_count_subquery,
            followers_count_subquery.c.followed_id == User.id,
        )
        .where(User.role == UserRole.master)
        .where(
            ~exists(
                select(1)
                .select_from(UserRestriction)
                .where(
                    UserRestriction.user_id == User.id,
                    UserRestriction.is_active.is_(True),
                    UserRestriction.restriction_type.in_(
                        [RestrictionType.profile_hidden, RestrictionType.full_block]
                    ),
                )
            )
        )
    )

    if search:
        pattern = f'%{search.strip()}%'
        stmt = stmt.where(
            or_(
                Profile.nickname.ilike(pattern),
                Profile.bio.ilike(pattern),
                MasterProfile.description.ilike(pattern),
                primary_workplace.studio_name.ilike(pattern),
                primary_workplace.public_text_override.ilike(pattern),
                MetroStation.name.ilike(pattern),
                MetroStation.line_name.ilike(pattern),
            )
        )

    if style_ids:
        stmt = stmt.where(
            exists(
                select(1)
                .select_from(SketchStyle)
                .join(Sketch, Sketch.id == SketchStyle.sketch_id)
                .where(
                    Sketch.author_id == User.id,
                    SketchStyle.style_id.in_(style_ids),
                )
            )
        )

    if tag_ids:
        stmt = stmt.where(
            exists(
                select(1)
                .select_from(SketchTag)
                .join(Sketch, Sketch.id == SketchTag.sketch_id)
                .where(
                    Sketch.author_id == User.id,
                    SketchTag.tag_id.in_(tag_ids),
                )
            )
        )

    if min_rating is not None:
        stmt = stmt.where(MasterProfile.rating_avg >= min_rating)

    if max_price is not None:
        stmt = stmt.where(
            or_(
                MasterProfile.price_min.is_(None),
                MasterProfile.price_min <= max_price,
            )
        )

    if city_location_id:
        city = db.execute(select(Location).where(Location.id == city_location_id)).scalar_one_or_none()
        if city:
            stmt = stmt.where(workplace_location.locality == city.locality)

    if region_location_id:
        region = db.execute(select(Location).where(Location.id == region_location_id)).scalar_one_or_none()
        if region and region.region:
            stmt = stmt.where(workplace_location.region == region.region)

    if center_lat is not None and center_lon is not None and radius_meters is not None:
        lat_delta = radius_meters / 111_320
        lon_delta = radius_meters / 111_320
        stmt = stmt.where(
            workplace_location.lat.between(center_lat - lat_delta, center_lat + lat_delta),
            workplace_location.lon.between(center_lon - lon_delta, center_lon + lon_delta),
        )

    if verified_only:
        stmt = stmt.where(MasterProfile.is_verified.is_(True))

    if favorite_only:
        stmt = stmt.where(MasterProfile.is_favorite.is_(True))

    sort_options = {
        'rating_desc': MasterProfile.rating_avg.desc(),
        'rating_asc': MasterProfile.rating_avg.asc(),
        'followers_desc': desc('followers_count'),
        'works_desc': MasterProfile.completed_sessions_count.desc(),
        'price_asc': MasterProfile.price_min.asc().nullslast(),
        'price_desc': MasterProfile.price_max.desc().nullslast(),
        'experience_desc': MasterProfile.experience_years.desc().nullslast(),
        'newest': Profile.created_at.desc(),
    }
    stmt = stmt.order_by(sort_options.get(sort, MasterProfile.rating_avg.desc()), Profile.nickname.asc())

    rows = db.execute(stmt.offset(offset).limit(limit)).all()

    result = []
    for row in rows:
        workplace_stub = MasterWorkplace(
            studio_name=row.studio_name,
            public_display_mode=row.public_display_mode or WorkplaceDisplayMode.street,
            public_text_override=row.public_text_override,
            public_metro_station_id=row.public_metro_station_id,
        )
        metro_stub = None
        if row.metro_station_name:
            metro_stub = MetroStation(
                city_location_id=row.public_metro_station_id,
                name=row.metro_station_name,
                line_name=row.metro_line_name,
                color_hex=row.metro_color_hex or '#999999',
                lat=0,
                lon=0,
            )
        location_stub = None
        if row.locality:
            location_stub = Location(
                country='',
                region=row.region,
                locality=row.locality,
                address_line=row.address_line,
                lat=0,
                lon=0,
                precision_level='locality',
            )
        result.append(
            {
                'user_id': str(row.user_id),
                'nickname': row.nickname,
                'avatar_url': resolve_media_url(row.avatar_url) if row.avatar_url else None,
                'bio': row.bio,
                'master_description': row.master_description,
                'master_address': _workplace_public_address(workplace_stub, location_stub, metro_stub),
                'master_rating': float(row.rating_avg or 0),
                'master_completed_works': int(row.completed_sessions_count or 0),
                'price_min': row.price_min,
                'price_max': row.price_max,
                'experience_years': row.experience_years,
                'is_verified': bool(row.is_verified),
                'is_favorite': bool(row.is_favorite),
                'followers_count': int(row.followers_count or 0),
                'preview_image_url': resolve_media_url(row.preview_image_url) if row.preview_image_url else None,
                'is_subscribed': bool(row.is_subscribed),
            }
        )

    return result


def list_master_reviews(db: Session, target_user_id: str, *, limit: int = 20, offset: int = 0):
    master_req = aliased(InkmatchRequest)
    client_req = aliased(InkmatchRequest)
    reviewer_profile = aliased(Profile)

    rows = db.execute(
        select(
            InkmatchReview,
            Inkmatch.sketch_id,
            client_req.created_by_user_id.label('reviewer_user_id'),
            reviewer_profile.nickname.label('reviewer_nickname'),
            reviewer_profile.avatar_url.label('reviewer_avatar_url'),
        )
        .join(Inkmatch, Inkmatch.id == InkmatchReview.inkmatch_id)
        .join(master_req, master_req.id == Inkmatch.master_request_id)
        .join(client_req, client_req.id == Inkmatch.client_request_id)
        .outerjoin(reviewer_profile, reviewer_profile.user_id == client_req.created_by_user_id)
        .where(master_req.created_by_user_id == target_user_id)
        .order_by(InkmatchReview.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    review_ids = [row.InkmatchReview.id for row in rows]
    attachments_rows = db.execute(
        select(InkmatchReviewAttachment)
        .where(InkmatchReviewAttachment.review_id.in_(review_ids))
        .order_by(InkmatchReviewAttachment.created_at.asc())
    ).scalars().all() if review_ids else []

    attachments_by_review: dict[str, list[dict]] = {}
    for attachment in attachments_rows:
        key = str(attachment.review_id)
        attachments_by_review.setdefault(key, []).append(
            {
                'id': str(attachment.id),
                'file_url': resolve_media_url(attachment.file_url),
                'file_type': attachment.file_type.value,
            }
        )

    payload = []
    for row in rows:
        review = row.InkmatchReview
        payload.append(
            {
                'id': str(review.id),
                'sketch_id': str(row.sketch_id),
                'reviewer_user_id': str(row.reviewer_user_id),
                'reviewer_nickname': row.reviewer_nickname,
                'reviewer_avatar_url': resolve_media_url(row.reviewer_avatar_url) if row.reviewer_avatar_url else None,
                'rating_overall': int(review.rating_overall),
                'body': review.body,
                'created_at': review.created_at.isoformat(),
                'attachments': attachments_by_review.get(str(review.id), []),
            }
        )

    return payload
