from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models.enums import SearchMode, WorkplaceType
from app.models.profiles import InkmatchDefaults, MasterProfile
from app.models.sketches import FeedPreferredStyle, FeedPreferredTag, Style, Tag
from app.models.moderation import ModerationReason, UserWarning
from app.models.user import User
from app.schemas.activity import ActivityStatsOut
from app.schemas.account import (
    AccountOut,
    AccountUpdateIn,
    ChangePasswordIn,
    FeedPreferenceIn,
    FeedPreferenceOut,
    InkmatchDefaultsIn,
    InkmatchDefaultsOut,
    MasterProfileIn,
    MasterProfileOut,
)
from app.schemas.moderation import UserRestrictionOut, UserWarningOut
from app.services.activity_service import build_activity_stats
from app.services.restriction_service import list_user_restrictions

router = APIRouter()


@router.get('/me', response_model=AccountOut)
def get_me(current_user=Depends(get_current_user)):
    return {
        'id': str(current_user.id),
        'email': current_user.email,
        'phone': current_user.phone,
        'role': current_user.role.value,
        'is_verified': bool(current_user.is_verified),
    }


@router.patch('/me', response_model=AccountOut)
def update_me(payload: AccountUpdateIn, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.email is not None:
        email = payload.email.strip() or None
        if email:
            exists = db.execute(select(User).where(User.email == email, User.id != current_user.id)).scalar_one_or_none()
            if exists:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Email already in use')
        current_user.email = email

    if payload.phone is not None:
        phone = payload.phone.strip() or None
        if phone:
            exists = db.execute(select(User).where(User.phone == phone, User.id != current_user.id)).scalar_one_or_none()
            if exists:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Phone already in use')
        current_user.phone = phone

    db.commit()
    db.refresh(current_user)
    return {
        'id': str(current_user.id),
        'email': current_user.email,
        'phone': current_user.phone,
        'role': current_user.role.value,
        'is_verified': bool(current_user.is_verified),
    }


@router.post('/me/change-password', status_code=status.HTTP_204_NO_CONTENT)
def change_password(payload: ChangePasswordIn, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Wrong old password')
    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    return None


@router.get('/master-profile', response_model=MasterProfileOut)
def get_master_profile(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(select(MasterProfile).where(MasterProfile.user_id == current_user.id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Master profile not found')
    return {
        'user_id': str(row.user_id),
        'experience_years': row.experience_years,
        'price_min': row.price_min,
        'price_max': row.price_max,
        'description': row.description,
        'is_verified': bool(row.is_verified),
        'rating_avg': float(row.rating_avg),
        'completed_sessions_count': int(row.completed_sessions_count),
    }


@router.put('/master-profile', response_model=MasterProfileOut)
def upsert_master_profile(payload: MasterProfileIn, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(select(MasterProfile).where(MasterProfile.user_id == current_user.id)).scalar_one_or_none()
    if not row:
        row = MasterProfile(user_id=current_user.id)
        db.add(row)

    row.experience_years = payload.experience_years
    row.price_min = payload.price_min
    row.price_max = payload.price_max
    row.description = payload.description

    db.commit()
    db.refresh(row)
    return {
        'user_id': str(row.user_id),
        'experience_years': row.experience_years,
        'price_min': row.price_min,
        'price_max': row.price_max,
        'description': row.description,
        'is_verified': bool(row.is_verified),
        'rating_avg': float(row.rating_avg),
        'completed_sessions_count': int(row.completed_sessions_count),
    }


@router.get('/inkmatch-defaults', response_model=InkmatchDefaultsOut)
def get_inkmatch_defaults(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(select(InkmatchDefaults).where(InkmatchDefaults.user_id == current_user.id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Defaults not found')
    return {
        'user_id': str(row.user_id),
        'experience_years_min': row.experience_years_min,
        'rating_min': float(row.rating_min) if row.rating_min is not None else None,
        'workplace': row.workplace.value if row.workplace else None,
        'search_mode': row.search_mode.value,
        'city_location_id': str(row.city_location_id) if row.city_location_id else None,
        'region_location_id': str(row.region_location_id) if row.region_location_id else None,
        'radius_meters': row.radius_meters,
        'center_lat': float(row.center_lat) if row.center_lat is not None else None,
        'center_lon': float(row.center_lon) if row.center_lon is not None else None,
        'default_size_sm': row.default_size_sm,
        'default_price_min': row.default_price_min,
        'default_price_max': row.default_price_max,
    }


@router.put('/inkmatch-defaults', response_model=InkmatchDefaultsOut)
def upsert_inkmatch_defaults(payload: InkmatchDefaultsIn, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        search_mode = SearchMode(payload.search_mode)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid search_mode')

    workplace = None
    if payload.workplace:
        try:
            workplace = WorkplaceType(payload.workplace)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid workplace')

    row = db.execute(select(InkmatchDefaults).where(InkmatchDefaults.user_id == current_user.id)).scalar_one_or_none()
    if not row:
        row = InkmatchDefaults(user_id=current_user.id, search_mode=search_mode)
        db.add(row)

    row.experience_years_min = payload.experience_years_min
    row.rating_min = Decimal(str(payload.rating_min)) if payload.rating_min is not None else None
    row.workplace = workplace
    row.search_mode = search_mode
    row.city_location_id = payload.city_location_id
    row.region_location_id = payload.region_location_id
    row.radius_meters = payload.radius_meters
    row.center_lat = Decimal(str(payload.center_lat)) if payload.center_lat is not None else None
    row.center_lon = Decimal(str(payload.center_lon)) if payload.center_lon is not None else None
    row.default_size_sm = payload.default_size_sm
    row.default_price_min = payload.default_price_min
    row.default_price_max = payload.default_price_max

    db.commit()
    db.refresh(row)
    return {
        'user_id': str(row.user_id),
        'experience_years_min': row.experience_years_min,
        'rating_min': float(row.rating_min) if row.rating_min is not None else None,
        'workplace': row.workplace.value if row.workplace else None,
        'search_mode': row.search_mode.value,
        'city_location_id': str(row.city_location_id) if row.city_location_id else None,
        'region_location_id': str(row.region_location_id) if row.region_location_id else None,
        'radius_meters': row.radius_meters,
        'center_lat': float(row.center_lat) if row.center_lat is not None else None,
        'center_lon': float(row.center_lon) if row.center_lon is not None else None,
        'default_size_sm': row.default_size_sm,
        'default_price_min': row.default_price_min,
        'default_price_max': row.default_price_max,
    }


@router.get('/feed-preferences', response_model=FeedPreferenceOut)
def get_feed_preferences(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    styles = db.execute(
        select(FeedPreferredStyle.style_id).where(FeedPreferredStyle.user_id == current_user.id)
    ).scalars().all()
    tags = db.execute(
        select(FeedPreferredTag.tag_id).where(FeedPreferredTag.user_id == current_user.id)
    ).scalars().all()
    return {
        'user_id': str(current_user.id),
        'style_ids': [str(s) for s in styles],
        'tag_ids': [str(t) for t in tags],
    }


@router.put('/feed-preferences', response_model=FeedPreferenceOut)
def upsert_feed_preferences(payload: FeedPreferenceIn, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.style_ids:
        styles_count = db.execute(select(Style.id).where(Style.id.in_(payload.style_ids))).scalars().all()
        if len(styles_count) != len(set(payload.style_ids)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unknown style id')
    if payload.tag_ids:
        tags_count = db.execute(select(Tag.id).where(Tag.id.in_(payload.tag_ids))).scalars().all()
        if len(tags_count) != len(set(payload.tag_ids)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unknown tag id')

    db.execute(FeedPreferredStyle.__table__.delete().where(FeedPreferredStyle.user_id == current_user.id))
    db.execute(FeedPreferredTag.__table__.delete().where(FeedPreferredTag.user_id == current_user.id))

    for style_id in payload.style_ids:
        db.add(FeedPreferredStyle(user_id=current_user.id, style_id=style_id, weight=1))
    for tag_id in payload.tag_ids:
        db.add(FeedPreferredTag(user_id=current_user.id, tag_id=tag_id, weight=1))

    db.commit()
    return {
        'user_id': str(current_user.id),
        'style_ids': payload.style_ids,
        'tag_ids': payload.tag_ids,
    }


@router.get('/activity-stats', response_model=ActivityStatsOut)
def get_activity_stats(
    range_days: int = Query(default=30, ge=7, le=90),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if range_days not in {7, 30, 90}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='range_days must be 7, 30 or 90')
    return build_activity_stats(db, str(current_user.id), current_user.role, range_days)


@router.get('/restrictions', response_model=list[UserRestrictionOut])
def get_my_restrictions(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return list_user_restrictions(db, str(current_user.id))


def _warning_out(db: Session, row: UserWarning) -> dict:
    reason = None
    if row.reason_id:
        reason = db.execute(select(ModerationReason).where(ModerationReason.id == row.reason_id)).scalar_one_or_none()
    return {
        'id': str(row.id),
        'user_id': str(row.user_id),
        'issued_by_moderator_id': str(row.issued_by_moderator_id),
        'reason_id': str(row.reason_id) if row.reason_id else None,
        'reason_title': reason.title if reason else None,
        'reason_text': row.reason_text,
        'status': row.status,
        'related_restriction_id': str(row.related_restriction_id) if row.related_restriction_id else None,
        'created_at': row.created_at,
        'resolved_at': row.resolved_at,
    }


@router.get('/warnings', response_model=list[UserWarningOut])
def get_my_warnings(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(UserWarning)
        .where(UserWarning.user_id == current_user.id)
        .order_by(UserWarning.created_at.desc())
    ).scalars().all()
    return [_warning_out(db, row) for row in rows]
