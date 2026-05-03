from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.enums import RestrictionType, UserRole
from app.schemas.profile import MasterFeedItemOut, MasterReviewOut, ProfileCreate, ProfileFullOut, ProfileOut, ProfileUpdate
from app.schemas.verification import (
    VerificationDocumentOut,
    VerificationPersonalDataIn,
    VerificationRequestOut,
)
from app.services.media_service import delete_media_reference, resolve_media_url, upload_media
from app.services.profile_service import create_profile, get_profile, get_profile_full, list_master_reviews, list_masters_feed, update_profile
from app.services.restriction_service import enforce_not_restricted, get_active_restriction
from app.services.verification_service import (
    get_verification_request_payload,
    submit_verification_request,
    skip_verification_request,
    upsert_personal_data,
    upload_verification_document,
)

router = APIRouter()

ALLOWED_IMAGE_MIME = {'image/jpeg', 'image/png', 'image/webp'}
ALLOWED_VERIFICATION_MIME = {
    'application/pdf',
    'image/jpeg',
    'image/png',
    'image/webp',
}


@router.get('/masters', response_model=list[MasterFeedItemOut])
def list_master_profiles(
    q: str | None = Query(default=None, min_length=1, max_length=64),
    style_ids: str | None = Query(default=None),
    tag_ids: str | None = Query(default=None),
    min_rating: float | None = Query(default=None, ge=0, le=5),
    max_price: int | None = Query(default=None, ge=0),
    city_location_id: str | None = Query(default=None),
    region_location_id: str | None = Query(default=None),
    center_lat: float | None = Query(default=None),
    center_lon: float | None = Query(default=None),
    radius_meters: int | None = Query(default=None, ge=0),
    verified_only: bool | None = Query(default=None),
    favorite_only: bool | None = Query(default=None),
    sort: str = Query(
        default='rating_desc',
        pattern='^(rating_desc|rating_asc|followers_desc|works_desc|price_asc|price_desc|experience_desc|newest)$',
    ),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parsed_style_ids = [item.strip() for item in (style_ids or '').split(',') if item.strip()]
    parsed_tag_ids = [item.strip() for item in (tag_ids or '').split(',') if item.strip()]

    return list_masters_feed(
        db,
        current_user_id=str(current_user.id),
        search=q,
        style_ids=parsed_style_ids or None,
        tag_ids=parsed_tag_ids or None,
        min_rating=min_rating,
        max_price=max_price,
        city_location_id=city_location_id,
        region_location_id=region_location_id,
        center_lat=center_lat,
        center_lon=center_lon,
        radius_meters=radius_meters,
        verified_only=verified_only,
        favorite_only=favorite_only,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.post('/me/avatar', response_model=ProfileOut)
async def upload_my_avatar(
    request: Request,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_not_restricted(db, str(current_user.id))
    profile = get_profile(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Profile not found')

    mime_type = (file.content_type or '').lower()
    if mime_type not in ALLOWED_IMAGE_MIME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Unsupported avatar type. Use jpeg/png/webp.',
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Empty file')

    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Avatar size exceeds 8MB limit')

    if profile.avatar_url:
        delete_media_reference(profile.avatar_url)

    profile.avatar_url = upload_media(content, 'avatars', str(current_user.id), mime_type=mime_type)
    db.commit()
    db.refresh(profile)
    return _profile_to_payload(profile)


def _profile_to_payload(profile):
    return {
        'user_id': str(profile.user_id),
        'nickname': profile.nickname,
        'avatar_url': resolve_media_url(profile.avatar_url) if profile.avatar_url else None,
        'bio': profile.bio,
        'home_location_id': str(profile.home_location_id) if profile.home_location_id else None,
        'default_currency': profile.default_currency,
    }


@router.get('/me', response_model=ProfileOut)
def get_my_profile(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    profile = get_profile(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Profile not found')
    return _profile_to_payload(profile)


@router.get('/me/full', response_model=ProfileFullOut)
def get_my_profile_full(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    payload = get_profile_full(db, str(current_user.id), str(current_user.id))
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Profile not found')
    return payload


@router.post('/me', response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
def create_my_profile(
    payload: ProfileCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_not_restricted(db, str(current_user.id))
    existing = get_profile(db, current_user.id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Profile already exists')
    profile = create_profile(db, current_user.id, payload.model_dump())
    return _profile_to_payload(profile)


@router.patch('/me', response_model=ProfileOut)
def update_my_profile(
    payload: ProfileUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_not_restricted(db, str(current_user.id))
    profile = get_profile(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Profile not found')

    incoming = payload.model_dump()
    next_nickname = incoming.get('nickname')
    if next_nickname is not None and next_nickname != profile.nickname:
        nickname_exists = db.execute(
            select(Profile.user_id).where(
                func.lower(Profile.nickname) == next_nickname.strip().lower(),
                Profile.user_id != current_user.id,
            )
        ).scalar_one_or_none()
        if nickname_exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Nickname already registered',
            )
        if profile.nickname_changed_at is not None:
            allowed_at = profile.nickname_changed_at + timedelta(days=14)
            from datetime import datetime, timezone
            if datetime.now(timezone.utc) < allowed_at:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Nickname can be changed once every 14 days',
                )
        from datetime import datetime, timezone
        profile.nickname_changed_at = datetime.now(timezone.utc)

    profile = update_profile(db, profile, incoming)
    return _profile_to_payload(profile)


def _require_master(current_user):
    if current_user.role != UserRole.master:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Master role required')


@router.get('/me/verification', response_model=VerificationRequestOut)
def get_my_verification_request(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    _require_master(current_user)
    return get_verification_request_payload(db, str(current_user.id))


@router.put('/me/verification/personal-data', response_model=VerificationRequestOut)
def save_my_verification_personal_data(
    payload: VerificationPersonalDataIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_master(current_user)
    enforce_not_restricted(db, str(current_user.id))
    try:
        upsert_personal_data(db, str(current_user.id), payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return get_verification_request_payload(db, str(current_user.id))


@router.post('/me/verification/documents', response_model=VerificationDocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_my_verification_document(
    document_type: str = Form(...),
    title: str | None = Form(default=None),
    issuer: str | None = Form(default=None),
    issued_date: str | None = Form(default=None),
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_master(current_user)
    enforce_not_restricted(db, str(current_user.id))
    mime_type = (file.content_type or '').lower()
    if mime_type not in ALLOWED_VERIFICATION_MIME:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported document type. Use pdf/jpeg/png/webp.')
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Empty file')
    if len(content) > 12 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Document size exceeds 12MB limit')
    parsed_issued_date = None
    if issued_date:
        try:
            parsed_issued_date = date.fromisoformat(issued_date)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid issued_date. Use YYYY-MM-DD') from exc

    try:
        file_row, document_row = upload_verification_document(
            db,
            str(current_user.id),
            document_type=document_type,
            title=title,
            issuer=issuer,
            issued_date=parsed_issued_date,
            content=content,
            mime_type=mime_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {
        'id': str(file_row.id),
        'document_id': str(document_row.id),
        'document_type': document_row.document_type.value,
        'title': document_row.title,
        'issuer': document_row.issuer,
        'issued_date': document_row.issued_date,
        'file_url': resolve_media_url(file_row.file_url),
        'file_type': file_row.file_type,
        'created_at': file_row.created_at.isoformat(),
    }


@router.post('/me/verification/submit', response_model=VerificationRequestOut)
def submit_my_verification_request(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    _require_master(current_user)
    enforce_not_restricted(db, str(current_user.id))
    try:
        submit_verification_request(db, str(current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return get_verification_request_payload(db, str(current_user.id))


@router.post('/me/verification/skip', response_model=VerificationRequestOut)
def skip_my_verification_request(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    _require_master(current_user)
    enforce_not_restricted(db, str(current_user.id))
    try:
        skip_verification_request(db, str(current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return get_verification_request_payload(db, str(current_user.id))




@router.get('/{user_id}/reviews', response_model=list[MasterReviewOut])
def get_master_reviews_by_user_id(
    user_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    return list_master_reviews(db, user_id, limit=limit, offset=offset)


@router.get('/{user_id}', response_model=ProfileOut)
def get_profile_by_user_id(user_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if str(current_user.id) != str(user_id):
        hidden = get_active_restriction(
            db,
            user_id,
            {RestrictionType.profile_hidden, RestrictionType.full_block},
        )
        if hidden:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Profile not found')
    profile = get_profile(db, user_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Profile not found')
    return _profile_to_payload(profile)


@router.get('/{user_id}/full', response_model=ProfileFullOut)
def get_profile_full_by_user_id(user_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    payload = get_profile_full(db, user_id, str(current_user.id))
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Profile not found')
    return payload

