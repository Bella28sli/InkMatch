from datetime import timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.enums import (
    InkmatchRequestStatus,
    InkmatchStatus,
    RequestCreatorRole,
    NotificationType,
    RestrictionType,
    SearchMode,
    WorkplaceType,
)
from app.models.enums import FileType
from app.models.profiles import MasterProfile
from app.models.inkmatch import (
    ClientInkmatchParams,
    Inkmatch,
    InkmatchRequest,
    InkmatchReview,
    InkmatchReviewAttachment,
    MasterInkmatchOffer,
)
from app.models.sketches import SketchMedia
from app.schemas.engagement import FileAttachmentIn, FileAttachmentOut
from app.schemas.inkmatch import (
    ClientInkmatchParamsIn,
    ClientInkmatchParamsOut,
    InkmatchCreateIn,
    InkmatchOut,
    InkmatchRequestCreateIn,
    InkmatchRequestOut,
    InkmatchRequestUpdateIn,
    InkmatchReviewIn,
    InkmatchReviewOut,
    MasterInkmatchOfferIn,
    MasterInkmatchOfferOut,
)
from app.services.inkmatch_service import debug_match_report, try_auto_match_for_request
from app.services.collection_service import add_collection_item, ensure_inkmatch_collection
from app.services.media_service import delete_media_reference, normalize_media_reference, resolve_media_url
from app.services.notification_service import create_notification
from app.services.restriction_service import enforce_not_restricted
from app.services.preference_weight_service import apply_preference_action

router = APIRouter()


def _request_out(row: InkmatchRequest):
    return {
        'id': str(row.id),
        'created_by_user_id': str(row.created_by_user_id),
        'created_by_role': row.created_by_role.value,
        'sketch_id': str(row.sketch_id),
        'status': row.status.value,
        'created_at': row.created_at.astimezone(timezone.utc).isoformat(),
        'updated_at': row.updated_at.astimezone(timezone.utc).isoformat(),
    }


def _inkmatch_out(row: Inkmatch):
    return {
        'id': str(row.id),
        'sketch_id': str(row.sketch_id),
        'client_request_id': str(row.client_request_id),
        'master_request_id': str(row.master_request_id),
        'chat_id': str(row.chat_id) if row.chat_id else None,
        'client_confirmed': bool(row.client_confirmed),
        'master_confirmed': bool(row.master_confirmed),
        'confirmed_at': row.confirmed_at.astimezone(timezone.utc).isoformat() if row.confirmed_at else None,
        'status': row.status.value,
        'created_at': row.created_at.astimezone(timezone.utc).isoformat(),
    }


@router.get('/requests/me', response_model=list[InkmatchRequestOut])
def list_my_requests(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(InkmatchRequest)
        .where(InkmatchRequest.created_by_user_id == current_user.id)
        .order_by(InkmatchRequest.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()
    return [_request_out(r) for r in rows]


@router.post('/requests', response_model=InkmatchRequestOut, status_code=status.HTTP_201_CREATED)
def create_request(payload: InkmatchRequestCreateIn, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.inkmatch_disabled)
    try:
        role = RequestCreatorRole(payload.created_by_role)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid created_by_role')

    row = InkmatchRequest(
        created_by_user_id=current_user.id,
        created_by_role=role,
        sketch_id=payload.sketch_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    try_auto_match_for_request(db, str(row.id))
    apply_preference_action(db, str(current_user.id), str(payload.sketch_id), 'request')

    # Store requested sketch in user's private InkMatch collection.
    try:
        inkmatch_collection = ensure_inkmatch_collection(db, str(current_user.id))
        db.commit()
        add_collection_item(
            db,
            str(inkmatch_collection.id),
            str(current_user.id),
            str(payload.sketch_id),
            None,
        )
    except Exception:
        db.rollback()

    create_notification(
        db,
        user_id=str(current_user.id),
        type_=NotificationType.inkmatch,
        title='Заявка InkMatch создана',
        body='Ваша заявка InkMatch активна.',
        deep_link=f'/inkmatch-request/{row.id}',
        image_url=_sketch_preview_url(db, str(payload.sketch_id)),
        links=[('inkmatch_request', str(row.id)), ('sketch', str(payload.sketch_id))],
        send_push_too=False,
    )
    db.commit()
    return _request_out(row)


@router.get('/requests/{request_id}', response_model=InkmatchRequestOut)
def get_request(request_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(select(InkmatchRequest).where(InkmatchRequest.id == request_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Request not found')
    if str(row.created_by_user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')
    return _request_out(row)


@router.get('/requests/{request_id}/client-params', response_model=ClientInkmatchParamsOut)
def get_client_params(request_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(select(InkmatchRequest).where(InkmatchRequest.id == request_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Request not found')
    if str(row.created_by_user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    params = db.execute(select(ClientInkmatchParams).where(ClientInkmatchParams.request_id == request_id)).scalar_one_or_none()
    if not params:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Client params not found')

    return {
        'request_id': str(params.request_id),
        'size_sm': params.size_sm,
        'price_min': params.price_min,
        'price_max': params.price_max,
        'search_mode': params.search_mode.value,
        'city_location_id': str(params.city_location_id) if params.city_location_id else None,
        'region_location_id': str(params.region_location_id) if params.region_location_id else None,
        'center_lat': float(params.center_lat) if params.center_lat is not None else None,
        'center_lon': float(params.center_lon) if params.center_lon is not None else None,
        'radius_meters': params.radius_meters,
        'preferred_experience_years_min': params.preferred_experience_years_min,
        'preferred_rating_min': float(params.preferred_rating_min) if params.preferred_rating_min is not None else None,
        'preferred_workplace': params.preferred_workplace.value if params.preferred_workplace else None,
    }


def _sketch_preview_url(db: Session, sketch_id: str) -> str | None:
    raw = db.execute(
        select(SketchMedia.url)
        .where(SketchMedia.sketch_id == sketch_id)
        .order_by(SketchMedia.sort_order.asc(), SketchMedia.created_at.asc())
        .limit(1)
    ).scalar_one_or_none()
    return resolve_media_url(raw) if raw else None


@router.get('/requests/{request_id}/offer', response_model=MasterInkmatchOfferOut)
def get_master_offer(request_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(select(InkmatchRequest).where(InkmatchRequest.id == request_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Request not found')
    if str(row.created_by_user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    offer = db.execute(select(MasterInkmatchOffer).where(MasterInkmatchOffer.request_id == request_id)).scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Master offer not found')

    return {
        'request_id': str(offer.request_id),
        'offer_price': offer.offer_price,
        'offer_duration_minutes': offer.offer_duration_minutes,
    }


@router.get('/requests/{request_id}/match', response_model=InkmatchOut | None)
def get_request_match(request_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(select(InkmatchRequest).where(InkmatchRequest.id == request_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Request not found')
    if str(row.created_by_user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    match = db.execute(
        select(Inkmatch).where(
            (Inkmatch.client_request_id == request_id) | (Inkmatch.master_request_id == request_id)
        )
    ).scalar_one_or_none()
    if not match:
        return None
    return _inkmatch_out(match)


@router.get('/requests/{request_id}/debug-match')
def debug_request_match(
    request_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.execute(select(InkmatchRequest).where(InkmatchRequest.id == request_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Request not found')
    if str(row.created_by_user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')
    return debug_match_report(db, request_id, limit=3)


@router.patch('/requests/{request_id}', response_model=InkmatchRequestOut)
def update_request(
    request_id: str,
    payload: InkmatchRequestUpdateIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.inkmatch_disabled)
    row = db.execute(select(InkmatchRequest).where(InkmatchRequest.id == request_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Request not found')
    if str(row.created_by_user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    try:
        row.status = InkmatchRequestStatus(payload.status)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid status')

    db.commit()
    db.refresh(row)
    return _request_out(row)


@router.delete('/requests/{request_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_request(request_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.inkmatch_disabled)
    row = db.execute(select(InkmatchRequest).where(InkmatchRequest.id == request_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Request not found')
    if str(row.created_by_user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')
    db.delete(row)
    db.commit()
    return None


@router.put('/requests/{request_id}/client-params', response_model=ClientInkmatchParamsOut)
def upsert_client_params(
    request_id: str,
    payload: ClientInkmatchParamsIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.inkmatch_disabled)
    request = db.execute(select(InkmatchRequest).where(InkmatchRequest.id == request_id)).scalar_one_or_none()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Request not found')
    if str(request.created_by_user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    try:
        search_mode = SearchMode(payload.search_mode)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid search_mode')

    workplace = None
    if payload.preferred_workplace:
        try:
            workplace = WorkplaceType(payload.preferred_workplace)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid preferred_workplace')

    row = db.execute(select(ClientInkmatchParams).where(ClientInkmatchParams.request_id == request_id)).scalar_one_or_none()
    if not row:
        row = ClientInkmatchParams(request_id=request_id, search_mode=search_mode)
        db.add(row)

    row.size_sm = payload.size_sm
    row.price_min = payload.price_min
    row.price_max = payload.price_max
    row.search_mode = search_mode
    row.city_location_id = payload.city_location_id
    row.region_location_id = payload.region_location_id
    row.center_lat = Decimal(str(payload.center_lat)) if payload.center_lat is not None else None
    row.center_lon = Decimal(str(payload.center_lon)) if payload.center_lon is not None else None
    row.radius_meters = payload.radius_meters
    row.preferred_experience_years_min = payload.preferred_experience_years_min
    row.preferred_rating_min = Decimal(str(payload.preferred_rating_min)) if payload.preferred_rating_min is not None else None
    row.preferred_workplace = workplace

    db.commit()
    db.refresh(row)

    result = {
        'request_id': str(row.request_id),
        'size_sm': row.size_sm,
        'price_min': row.price_min,
        'price_max': row.price_max,
        'search_mode': row.search_mode.value,
        'city_location_id': str(row.city_location_id) if row.city_location_id else None,
        'region_location_id': str(row.region_location_id) if row.region_location_id else None,
        'center_lat': float(row.center_lat) if row.center_lat is not None else None,
        'center_lon': float(row.center_lon) if row.center_lon is not None else None,
        'radius_meters': row.radius_meters,
        'preferred_experience_years_min': row.preferred_experience_years_min,
        'preferred_rating_min': float(row.preferred_rating_min) if row.preferred_rating_min is not None else None,
        'preferred_workplace': row.preferred_workplace.value if row.preferred_workplace else None,
    }
    try_auto_match_for_request(db, request_id)
    return result


@router.put('/requests/{request_id}/offer', response_model=MasterInkmatchOfferOut)
def upsert_master_offer(
    request_id: str,
    payload: MasterInkmatchOfferIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.inkmatch_disabled)
    request = db.execute(select(InkmatchRequest).where(InkmatchRequest.id == request_id)).scalar_one_or_none()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Request not found')
    if str(request.created_by_user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    row = db.execute(select(MasterInkmatchOffer).where(MasterInkmatchOffer.request_id == request_id)).scalar_one_or_none()
    if not row:
        row = MasterInkmatchOffer(request_id=request_id, offer_price=payload.offer_price, offer_duration_minutes=payload.offer_duration_minutes)
        db.add(row)
    else:
        row.offer_price = payload.offer_price
        row.offer_duration_minutes = payload.offer_duration_minutes

    db.commit()
    db.refresh(row)
    result = {
        'request_id': str(row.request_id),
        'offer_price': row.offer_price,
        'offer_duration_minutes': row.offer_duration_minutes,
    }
    try_auto_match_for_request(db, request_id)
    return result


@router.get('/matches/me', response_model=list[InkmatchOut])
def list_my_matches(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    my_request_ids = db.execute(
        select(InkmatchRequest.id).where(InkmatchRequest.created_by_user_id == current_user.id)
    ).scalars().all()

    if not my_request_ids:
        return []

    rows = db.execute(
        select(Inkmatch)
        .where(
            (Inkmatch.client_request_id.in_(my_request_ids))
            | (Inkmatch.master_request_id.in_(my_request_ids))
        )
        .order_by(Inkmatch.created_at.desc())
    ).scalars().all()

    return [_inkmatch_out(r) for r in rows]


@router.post('/matches', response_model=InkmatchOut, status_code=status.HTTP_201_CREATED)
def create_match(payload: InkmatchCreateIn, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.inkmatch_disabled)
    client_req = db.execute(select(InkmatchRequest).where(InkmatchRequest.id == payload.client_request_id)).scalar_one_or_none()
    master_req = db.execute(select(InkmatchRequest).where(InkmatchRequest.id == payload.master_request_id)).scalar_one_or_none()
    if not client_req or not master_req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Request not found')
    if str(client_req.created_by_user_id) != str(current_user.id) and str(master_req.created_by_user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    row = Inkmatch(
        sketch_id=payload.sketch_id,
        client_request_id=payload.client_request_id,
        master_request_id=payload.master_request_id,
        status=InkmatchStatus.active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _inkmatch_out(row)


@router.patch('/matches/{match_id}/status', response_model=InkmatchOut)
def update_match_status(
    match_id: str,
    status_value: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.inkmatch_disabled)
    row = db.execute(select(Inkmatch).where(Inkmatch.id == match_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Match not found')

    my_request_ids = set(
        str(i)
        for i in db.execute(
            select(InkmatchRequest.id).where(InkmatchRequest.created_by_user_id == current_user.id)
        ).scalars().all()
    )
    if str(row.client_request_id) not in my_request_ids and str(row.master_request_id) not in my_request_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    try:
        row.status = InkmatchStatus(status_value)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid status')

    db.commit()
    db.refresh(row)
    return _inkmatch_out(row)


@router.get('/reviews/me', response_model=list[InkmatchReviewOut])
def list_my_reviews(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    my_request_ids = db.execute(
        select(InkmatchRequest.id).where(InkmatchRequest.created_by_user_id == current_user.id)
    ).scalars().all()

    if not my_request_ids:
        return []

    match_ids = db.execute(
        select(Inkmatch.id).where(
            (Inkmatch.client_request_id.in_(my_request_ids))
            | (Inkmatch.master_request_id.in_(my_request_ids))
        )
    ).scalars().all()
    if not match_ids:
        return []

    rows = db.execute(
        select(InkmatchReview)
        .where(InkmatchReview.inkmatch_id.in_(match_ids))
        .order_by(InkmatchReview.created_at.desc())
    ).scalars().all()

    return [
        {
            'id': str(r.id),
            'inkmatch_id': str(r.inkmatch_id),
            'rating_overall': r.rating_overall,
            'rating_communication': r.rating_communication,
            'rating_cleanliness': r.rating_cleanliness,
            'rating_quality': r.rating_quality,
            'rating_punctuality': r.rating_punctuality,
            'rating_price_fairness': r.rating_price_fairness,
            'body': r.body,
            'created_at': r.created_at.astimezone(timezone.utc).isoformat(),
            'updated_at': r.updated_at.astimezone(timezone.utc).isoformat(),
        }
        for r in rows
    ]


@router.post('/reviews', response_model=InkmatchReviewOut, status_code=status.HTTP_201_CREATED)
def create_review(payload: InkmatchReviewIn, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.inkmatch_disabled)
    match_row = db.execute(select(Inkmatch).where(Inkmatch.id == payload.inkmatch_id)).scalar_one_or_none()
    if not match_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Match not found')

    my_request_ids = set(
        str(i)
        for i in db.execute(
            select(InkmatchRequest.id).where(InkmatchRequest.created_by_user_id == current_user.id)
        ).scalars().all()
    )
    if str(match_row.client_request_id) not in my_request_ids and str(match_row.master_request_id) not in my_request_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    client_req = db.execute(select(InkmatchRequest).where(InkmatchRequest.id == match_row.client_request_id)).scalar_one_or_none()
    if not client_req or str(client_req.created_by_user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only client can leave review')
    if not match_row.client_confirmed or not match_row.master_confirmed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Both sides must confirm booking first')

    exists = db.execute(
        select(InkmatchReview).where(InkmatchReview.inkmatch_id == payload.inkmatch_id)
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Review already exists')

    row = InkmatchReview(
        inkmatch_id=payload.inkmatch_id,
        rating_overall=payload.rating_overall,
        rating_communication=payload.rating_communication,
        rating_cleanliness=payload.rating_cleanliness,
        rating_quality=payload.rating_quality,
        rating_punctuality=payload.rating_punctuality,
        rating_price_fairness=payload.rating_price_fairness,
        body=payload.body,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    master_req = db.execute(
        select(InkmatchRequest).where(InkmatchRequest.id == match_row.master_request_id)
    ).scalar_one_or_none()
    if master_req:
        master_user_id = master_req.created_by_user_id
        rating_avg, reviews_count = db.execute(
            select(func.avg(InkmatchReview.rating_overall), func.count(InkmatchReview.id))
            .join(Inkmatch, Inkmatch.id == InkmatchReview.inkmatch_id)
            .join(InkmatchRequest, InkmatchRequest.id == Inkmatch.master_request_id)
            .where(InkmatchRequest.created_by_user_id == master_user_id)
        ).one()

        master_profile = db.execute(
            select(MasterProfile).where(MasterProfile.user_id == master_user_id)
        ).scalar_one_or_none()
        if master_profile:
            master_profile.rating_avg = float(rating_avg or 0)
            master_profile.completed_sessions_count = int(reviews_count or 0)

        create_notification(
            db,
            user_id=str(master_user_id),
            type_=NotificationType.session,
            title='Новый отзыв',
            body='Клиент оставил отзыв по подтвержденной заявке InkMatch.',
            deep_link='/profile/me',
            image_url=_sketch_preview_url(db, str(match_row.sketch_id)),
            links=[('review', str(row.id)), ('inkmatch', str(match_row.id))],
        )
        db.commit()

    return {
        'id': str(row.id),
        'inkmatch_id': str(row.inkmatch_id),
        'rating_overall': row.rating_overall,
        'rating_communication': row.rating_communication,
        'rating_cleanliness': row.rating_cleanliness,
        'rating_quality': row.rating_quality,
        'rating_punctuality': row.rating_punctuality,
        'rating_price_fairness': row.rating_price_fairness,
        'body': row.body,
        'created_at': row.created_at.astimezone(timezone.utc).isoformat(),
        'updated_at': row.updated_at.astimezone(timezone.utc).isoformat(),
    }


@router.get('/reviews/{review_id}/attachments', response_model=list[FileAttachmentOut])
def list_review_attachments(review_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    review = db.execute(select(InkmatchReview).where(InkmatchReview.id == review_id)).scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Review not found')

    my_request_ids = set(
        str(i)
        for i in db.execute(
            select(InkmatchRequest.id).where(InkmatchRequest.created_by_user_id == current_user.id)
        ).scalars().all()
    )
    match_row = db.execute(select(Inkmatch).where(Inkmatch.id == review.inkmatch_id)).scalar_one_or_none()
    if not match_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Match not found')
    if str(match_row.client_request_id) not in my_request_ids and str(match_row.master_request_id) not in my_request_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    rows = db.execute(select(InkmatchReviewAttachment).where(InkmatchReviewAttachment.review_id == review_id)).scalars().all()
    return [
        {
            'id': str(r.id),
            'file_url': resolve_media_url(r.file_url),
            'file_type': r.file_type.value,
            'mime_type': None,
            'file_size_bytes': None,
            'width': None,
            'height': None,
            'duration_seconds': None,
        }
        for r in rows
    ]


@router.post('/reviews/{review_id}/attachments', response_model=FileAttachmentOut, status_code=status.HTTP_201_CREATED)
def add_review_attachment(
    review_id: str,
    payload: FileAttachmentIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_not_restricted(db, str(current_user.id), RestrictionType.inkmatch_disabled)
    review = db.execute(select(InkmatchReview).where(InkmatchReview.id == review_id)).scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Review not found')

    my_request_ids = set(
        str(i)
        for i in db.execute(
            select(InkmatchRequest.id).where(InkmatchRequest.created_by_user_id == current_user.id)
        ).scalars().all()
    )
    match_row = db.execute(select(Inkmatch).where(Inkmatch.id == review.inkmatch_id)).scalar_one_or_none()
    if not match_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Match not found')
    if str(match_row.client_request_id) not in my_request_ids and str(match_row.master_request_id) not in my_request_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    try:
        file_type = FileType(payload.file_type)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid file_type')

    row = InkmatchReviewAttachment(
        review_id=review_id,
        file_url=normalize_media_reference(payload.file_url),
        file_type=file_type,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        'id': str(row.id),
        'file_url': row.file_url,
        'file_type': row.file_type.value,
        'mime_type': None,
        'file_size_bytes': None,
        'width': None,
        'height': None,
        'duration_seconds': None,
    }


@router.delete('/reviews/attachments/{attachment_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_review_attachment(attachment_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(select(InkmatchReviewAttachment).where(InkmatchReviewAttachment.id == attachment_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Attachment not found')

    review = db.execute(select(InkmatchReview).where(InkmatchReview.id == row.review_id)).scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Review not found')

    my_request_ids = set(
        str(i)
        for i in db.execute(
            select(InkmatchRequest.id).where(InkmatchRequest.created_by_user_id == current_user.id)
        ).scalars().all()
    )
    match_row = db.execute(select(Inkmatch).where(Inkmatch.id == review.inkmatch_id)).scalar_one_or_none()
    if not match_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Match not found')
    if str(match_row.client_request_id) not in my_request_ids and str(match_row.master_request_id) not in my_request_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')

    delete_media_reference(row.file_url)
    db.delete(row)
    db.commit()
    return None
