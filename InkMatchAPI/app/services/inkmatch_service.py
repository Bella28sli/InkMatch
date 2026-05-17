from __future__ import annotations

from datetime import datetime, timezone
from math import cos, radians

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.enums import InkmatchRequestStatus, InkmatchStatus, NotificationType, RequestCreatorRole
from app.models.inkmatch import ClientInkmatchParams, Inkmatch, InkmatchRequest, MasterInkmatchOffer
from app.models.locations import Location, MasterWorkplace
from app.models.messaging import Message
from app.models.profiles import MasterProfile
from app.models.sketches import SketchMedia
from app.models.enums import MediaType
from app.services.chat_service import get_or_create_direct_chat
from app.services.notification_service import create_notification
from app.services.media_service import resolve_media_url


def _match_context(
    db: Session,
    *,
    sketch_id,
    master_request_id,
) -> dict:
    offer = db.execute(
        select(MasterInkmatchOffer).where(MasterInkmatchOffer.request_id == master_request_id)
    ).scalar_one_or_none()
    preview_row = db.execute(
        select(SketchMedia.preview_image_url, SketchMedia.url, SketchMedia.media_type)
        .where(SketchMedia.sketch_id == sketch_id)
        .where(SketchMedia.media_type == MediaType.image)
        .order_by(SketchMedia.sort_order.asc())
        .limit(1)
    ).one_or_none()
    if not preview_row:
        preview_row = db.execute(
            select(SketchMedia.preview_image_url, SketchMedia.url, SketchMedia.media_type)
            .where(SketchMedia.sketch_id == sketch_id)
            .order_by(SketchMedia.sort_order.asc())
            .limit(1)
        ).one_or_none()
    preview_url = None
    if preview_row:
        preview_url = preview_row[0] or preview_row[1]
    master_location = None
    master_request = db.execute(
        select(InkmatchRequest).where(InkmatchRequest.id == master_request_id)
    ).scalar_one_or_none()
    if master_request:
        workplace_row = db.execute(
            select(MasterWorkplace, Location)
            .join(Location, Location.id == MasterWorkplace.location_id)
            .where(
                MasterWorkplace.master_id == master_request.created_by_user_id,
                MasterWorkplace.is_primary.is_(True),
            )
            .limit(1)
        ).one_or_none()
        if workplace_row:
            workplace, location = workplace_row
            address = ', '.join(
                part for part in [workplace.studio_name, location.address_line, location.locality, location.region] if part
            )
            master_location = {
                'location_id': str(location.id),
                'address': address,
                'lat': float(workplace.public_lat if workplace.public_lat is not None else location.lat),
                'lon': float(workplace.public_lon if workplace.public_lon is not None else location.lon),
            }
    return {
        'sketch_preview_url': resolve_media_url(preview_url) if preview_url else None,
        'attachments': (
            [
                {
                    'file_url': resolve_media_url(preview_url) if preview_url else None,
                    'file_type': 'image',
                    'mime_type': 'image/jpeg',
                }
            ]
            if preview_url
            else []
        ),
        'offer_price': int(offer.offer_price) if offer else None,
        'offer_duration_minutes': int(offer.offer_duration_minutes) if offer else None,
        'master_location': master_location,
    }


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat_km = (lat1 - lat2) * 111.0
    lon_km = (lon1 - lon2) * 111.0 * cos(radians((lat1 + lat2) / 2.0))
    return (lat_km * lat_km + lon_km * lon_km) ** 0.5


def _master_primary_location(db: Session, master_user_id) -> Location | None:
    return db.execute(
        select(Location)
        .join(MasterWorkplace, MasterWorkplace.location_id == Location.id)
        .where(
            MasterWorkplace.master_id == master_user_id,
            MasterWorkplace.is_primary.is_(True),
        )
        .limit(1)
    ).scalar_one_or_none()


def _has_system_match_message(db: Session, chat_id, match_id: str) -> bool:
    return db.execute(
        select(Message.id).where(
            Message.chat_id == chat_id,
            Message.message_type == 'system_inkmatch',
            Message.payload['inkmatch_id'].astext == str(match_id),
        )
    ).scalar_one_or_none() is not None


def _compatibility_report(db: Session, client_request_id: str, master_request_id: str) -> dict:
    report: dict = {
        'compatible': False,
        'reason': None,
        'details': [],
    }

    def fail(reason: str, detail: str) -> dict:
        report['reason'] = reason
        report['details'].append(detail)
        return report

    params = db.execute(
        select(ClientInkmatchParams).where(ClientInkmatchParams.request_id == client_request_id)
    ).scalar_one_or_none()
    offer = db.execute(
        select(MasterInkmatchOffer).where(MasterInkmatchOffer.request_id == master_request_id)
    ).scalar_one_or_none()

    if not params:
        return fail('missing_client_params', 'У клиента не сохранены параметры InkMatch')
    if not offer:
        return fail('missing_master_offer', 'У мастера не сохранено предложение InkMatch')

    report['details'].append(
        f'Цена мастера {offer.offer_price} ₽, допустимый диапазон клиента: '
        f'{params.price_min if params.price_min is not None else "-"} - '
        f'{params.price_max if params.price_max is not None else "-"}'
    )
    if params.price_min is not None and offer.offer_price < params.price_min:
        return fail('price_too_low', 'Цена мастера ниже минимальной цены клиента')
    if params.price_max is not None and offer.offer_price > params.price_max:
        return fail('price_too_high', 'Цена мастера выше максимальной цены клиента')

    master_request = db.execute(
        select(InkmatchRequest).where(InkmatchRequest.id == master_request_id)
    ).scalar_one_or_none()
    if not master_request:
        return fail('missing_master_request', 'Не найдена заявка мастера')

    master_profile = db.execute(
        select(MasterProfile).where(MasterProfile.user_id == master_request.created_by_user_id)
    ).scalar_one_or_none()

    if params.preferred_experience_years_min is not None:
        experience = master_profile.experience_years if master_profile else None
        report['details'].append(
            f'Стаж мастера: {experience if experience is not None else "-"}, '
            f'минимум клиента: {params.preferred_experience_years_min}'
        )
        if not master_profile or (master_profile.experience_years or 0) < params.preferred_experience_years_min:
            return fail('experience_too_low', 'У мастера меньше опыта, чем требует клиент')

    if params.preferred_rating_min is not None:
        rating = float(master_profile.rating_avg or 0) if master_profile else 0.0
        report['details'].append(
            f'Рейтинг мастера: {rating:.2f}, минимум клиента: {float(params.preferred_rating_min):.2f}'
        )
        if not master_profile or rating < float(params.preferred_rating_min):
            return fail('rating_too_low', 'Рейтинг мастера ниже минимального требования клиента')

    master_location = _master_primary_location(db, master_request.created_by_user_id)
    if params.search_mode.value in {'city', 'region', 'radius'} and not master_location:
        return fail('missing_master_location', 'У мастера нет основной локации для проверки адреса')

    if params.search_mode.value == 'city' and params.city_location_id:
        city = db.execute(select(Location).where(Location.id == params.city_location_id)).scalar_one_or_none()
        if not city:
            return fail('missing_city_location', 'Не найдена выбранная клиентом локация города')
        report['details'].append(
            f'Проверка города: мастер {master_location.locality if master_location else "-"}, '
            f'клиент {city.locality}'
        )
        if master_location.locality != city.locality:
            return fail('city_mismatch', 'Город мастера не совпадает с городом клиента')

    if params.search_mode.value == 'region' and params.region_location_id:
        region = db.execute(select(Location).where(Location.id == params.region_location_id)).scalar_one_or_none()
        if not region:
            return fail('missing_region_location', 'Не найдена выбранная клиентом локация региона')
        report['details'].append(
            f'Проверка региона: мастер {master_location.region if master_location else "-"}, '
            f'клиент {region.region}'
        )
        if master_location.region != region.region:
            return fail('region_mismatch', 'Регион мастера не совпадает с регионом клиента')

    if params.search_mode.value == 'radius':
        if params.center_lat is None or params.center_lon is None or not params.radius_meters:
            return fail('missing_radius_data', 'У клиента не заполнены координаты или радиус поиска')
        distance = _distance_km(
            float(params.center_lat),
            float(params.center_lon),
            float(master_location.lat),
            float(master_location.lon),
        )
        report['details'].append(
            f'Проверка радиуса: расстояние {distance:.2f} км, '
            f'радиус клиента {params.radius_meters / 1000:.2f} км'
        )
        if distance > params.radius_meters / 1000:
            return fail('radius_too_far', 'Локация мастера находится дальше радиуса клиента')

    report['compatible'] = True
    report['reason'] = 'compatible'
    report['details'].append('Все проверки пройдены')
    return report

def try_auto_match_for_request(db: Session, request_id: str) -> Inkmatch | None:
    source = db.execute(
        select(InkmatchRequest).where(InkmatchRequest.id == request_id)
    ).scalar_one_or_none()
    if not source or source.status != InkmatchRequestStatus.active:
        return None

    counterpart_role = (
        RequestCreatorRole.master
        if source.created_by_role == RequestCreatorRole.client
        else RequestCreatorRole.client
    )

    candidates = db.execute(
        select(InkmatchRequest)
        .where(
            InkmatchRequest.sketch_id == source.sketch_id,
            InkmatchRequest.created_by_role == counterpart_role,
            InkmatchRequest.status == InkmatchRequestStatus.active,
            InkmatchRequest.created_by_user_id != source.created_by_user_id,
        )
        .order_by(InkmatchRequest.created_at.asc())
    ).scalars().all()

    for other in candidates:
        client_req = source if source.created_by_role == RequestCreatorRole.client else other
        master_req = source if source.created_by_role == RequestCreatorRole.master else other

        existing = db.execute(
            select(Inkmatch).where(
                Inkmatch.client_request_id == client_req.id,
                Inkmatch.master_request_id == master_req.id,
            )
        ).scalar_one_or_none()
        if existing:
            if existing.chat_id is None:
                chat = get_or_create_direct_chat(
                    db,
                    str(client_req.created_by_user_id),
                    str(master_req.created_by_user_id),
                )
                existing.chat_id = chat.id
                context = _match_context(
                    db,
                    sketch_id=source.sketch_id,
                    master_request_id=master_req.id,
                )
                if not _has_system_match_message(db, chat.id, str(existing.id)):
                    db.add(
                        Message(
                            chat_id=chat.id,
                            sender_id=None,
                            message_type='system_inkmatch',
                            text=(
                                'Найдена совпавшая заявка InkMatch. '
                                f'Предложение мастера: {context["offer_price"] if context["offer_price"] is not None else "-"} ₽, '
                                f'{context["offer_duration_minutes"] if context["offer_duration_minutes"] is not None else "-"} мин. '
                                'Проверьте пост и подтвердите или отмените запись.'
                            ),
                            payload={
                                'inkmatch_id': str(existing.id),
                                'client_request_id': str(client_req.id),
                                'master_request_id': str(master_req.id),
                                'sketch_id': str(source.sketch_id),
                                'sketch_preview_url': context['sketch_preview_url'],
                                'attachments': context['attachments'],
                                'offer_price': context['offer_price'],
                                'offer_duration_minutes': context['offer_duration_minutes'],
                                'master_location': context['master_location'],
                                'action': 'match_created',
                            },
                        )
                    )
                db.commit()
                db.refresh(existing)
                create_notification(
                    db,
                    user_id=str(client_req.created_by_user_id),
                    type_=NotificationType.inkmatch,
                    title='Найден InkMatch',
                    body='Найдена совпавшая заявка. Откройте чат и подтвердите решение.',
                    deep_link=f'/inkmatch-request/{client_req.id}',
                    links=[
                        ('inkmatch', str(existing.id)),
                        ('inkmatch_request', str(client_req.id)),
                        ('chat', str(chat.id)),
                    ],
                )
                create_notification(
                    db,
                    user_id=str(master_req.created_by_user_id),
                    type_=NotificationType.inkmatch,
                    title='Найден InkMatch',
                    body='Найдена совпавшая заявка. Откройте чат и подтвердите решение.',
                    deep_link=f'/inkmatch-request/{master_req.id}',
                    links=[
                        ('inkmatch', str(existing.id)),
                        ('inkmatch_request', str(master_req.id)),
                        ('chat', str(chat.id)),
                    ],
                )
                db.commit()
            return existing

        if not _is_compatible(db, client_req.id, master_req.id):
            continue

        chat = get_or_create_direct_chat(
            db,
            str(client_req.created_by_user_id),
            str(master_req.created_by_user_id),
        )

        match = Inkmatch(
            sketch_id=source.sketch_id,
            client_request_id=client_req.id,
            master_request_id=master_req.id,
            chat_id=chat.id,
            status=InkmatchStatus.active,
            client_confirmed=False,
            master_confirmed=False,
            confirmed_at=None,
        )
        db.add(match)
        db.flush()

        client_req.status = InkmatchRequestStatus.matched
        master_req.status = InkmatchRequestStatus.matched

        context = _match_context(
            db,
            sketch_id=source.sketch_id,
            master_request_id=master_req.id,
        )
        offer_price = context['offer_price']
        offer_duration = context['offer_duration_minutes']

        summary_text = (
            'Найдена совпавшая заявка InkMatch. '
            f'Предложение мастера: {offer_price if offer_price is not None else "-"} ₽, '
            f'{offer_duration if offer_duration is not None else "-"} мин. '
            'Проверьте пост и подтвердите или отмените запись.'
        )
        db.add(
            Message(
                chat_id=chat.id,
                sender_id=None,
                message_type='system_inkmatch',
                text=summary_text,
                payload={
                    'inkmatch_id': str(match.id),
                    'client_request_id': str(client_req.id),
                    'master_request_id': str(master_req.id),
                    'sketch_id': str(source.sketch_id),
                    'sketch_preview_url': context['sketch_preview_url'],
                    'attachments': context['attachments'],
                    'offer_price': offer_price,
                    'offer_duration_minutes': offer_duration,
                    'master_location': context['master_location'],
                    'action': 'match_created',
                },
            )
        )

        db.commit()
        db.refresh(match)

        client_user_id = str(client_req.created_by_user_id)
        master_user_id = str(master_req.created_by_user_id)
        create_notification(
            db,
            user_id=client_user_id,
            type_=NotificationType.inkmatch,
            title='Найден InkMatch',
            body='Найдена совпавшая заявка. Откройте чат и подтвердите решение.',
            deep_link=f'/inkmatch-request/{client_req.id}',
            links=[
                ('inkmatch', str(match.id)),
                ('inkmatch_request', str(client_req.id)),
                ('chat', str(chat.id)),
            ],
        )
        create_notification(
            db,
            user_id=master_user_id,
            type_=NotificationType.inkmatch,
            title='Найден InkMatch',
            body='Найдена совпавшая заявка. Откройте чат и подтвердите решение.',
            deep_link=f'/inkmatch-request/{master_req.id}',
            links=[
                ('inkmatch', str(match.id)),
                ('inkmatch_request', str(master_req.id)),
                ('chat', str(chat.id)),
            ],
        )
        db.commit()
        return match

    return None


def confirm_match_from_chat(db: Session, match: Inkmatch, current_user_id: str) -> Inkmatch:
    client_request = db.execute(
        select(InkmatchRequest).where(InkmatchRequest.id == match.client_request_id)
    ).scalar_one_or_none()
    master_request = db.execute(
        select(InkmatchRequest).where(InkmatchRequest.id == match.master_request_id)
    ).scalar_one_or_none()

    if not client_request or not master_request:
        raise ValueError('InkMatch requests not found')

    current_user = str(current_user_id)
    changed = False

    if str(client_request.created_by_user_id) == current_user and not match.client_confirmed:
        match.client_confirmed = True
        changed = True
    elif str(master_request.created_by_user_id) == current_user and not match.master_confirmed:
        match.master_confirmed = True
        changed = True
    elif str(client_request.created_by_user_id) != current_user and str(master_request.created_by_user_id) != current_user:
        raise ValueError('User is not part of this InkMatch')

    if changed and not (match.client_confirmed and match.master_confirmed):
        target_user_id = (
            str(master_request.created_by_user_id)
            if str(client_request.created_by_user_id) == current_user
            else str(client_request.created_by_user_id)
        )
        create_notification(
            db,
            user_id=target_user_id,
            type_=NotificationType.inkmatch,
            title='Требуется подтверждение InkMatch',
            body='Другая сторона подтвердила запись. Подтвердите со своей стороны.',
            deep_link=f'/chat/{match.chat_id}',
            links=[('inkmatch', str(match.id)), ('chat', str(match.chat_id))],
        )

    if match.client_confirmed and match.master_confirmed and match.confirmed_at is None:
        context = _match_context(
            db,
            sketch_id=match.sketch_id,
            master_request_id=master_request.id,
        )
        match.confirmed_at = datetime.now(timezone.utc)
        db.add(
            Message(
                chat_id=match.chat_id,
                sender_id=None,
                message_type='system_inkmatch',
                text='Обе стороны подтвердили запись. Клиент может оставить отзыв о сеансе.',
                payload={
                    'inkmatch_id': str(match.id),
                    'action': 'both_confirmed',
                    'review_available': True,
                    'sketch_id': str(match.sketch_id),
                    'sketch_preview_url': context['sketch_preview_url'],
                    'attachments': context['attachments'],
                    'offer_price': context['offer_price'],
                    'offer_duration_minutes': context['offer_duration_minutes'],
                    'master_location': context['master_location'],
                },
            )
        )

        create_notification(
            db,
            user_id=str(client_request.created_by_user_id),
            type_=NotificationType.session,
            title='InkMatch подтвержден',
            body='Обе стороны подтвердили запись. Продолжайте общение в чате.',
            deep_link=f'/chat/{match.chat_id}',
            links=[('inkmatch', str(match.id)), ('chat', str(match.chat_id))],
        )
        create_notification(
            db,
            user_id=str(master_request.created_by_user_id),
            type_=NotificationType.session,
            title='InkMatch подтвержден',
            body='Обе стороны подтвердили запись. Продолжайте общение в чате.',
            deep_link=f'/chat/{match.chat_id}',
            links=[('inkmatch', str(match.id)), ('chat', str(match.chat_id))],
        )

    db.commit()
    db.refresh(match)
    return match


def cancel_match_from_chat(db: Session, match: Inkmatch) -> None:
    client_req = db.execute(
        select(InkmatchRequest).where(InkmatchRequest.id == match.client_request_id)
    ).scalar_one_or_none()
    master_req = db.execute(
        select(InkmatchRequest).where(InkmatchRequest.id == match.master_request_id)
    ).scalar_one_or_none()

    if client_req:
        client_req.status = InkmatchRequestStatus.active
    if master_req:
        master_req.status = InkmatchRequestStatus.active

    db.execute(
        Message.__table__.delete().where(
            and_(
                Message.chat_id == match.chat_id,
                Message.message_type == 'system_inkmatch',
                Message.payload['inkmatch_id'].astext == str(match.id),
            )
        )
    )

    client_user_id = str(client_req.created_by_user_id) if client_req else None
    master_user_id = str(master_req.created_by_user_id) if master_req else None

    db.delete(match)
    db.commit()

    for user_id in (client_user_id, master_user_id):
        if not user_id:
            continue
        create_notification(
            db,
            user_id=user_id,
            type_=NotificationType.inkmatch,
            title='InkMatch отменен',
            body='InkMatch был отменен.',
            deep_link='/inkmatch',
        )
    db.commit()


def _is_compatible(db: Session, client_request_id: str, master_request_id: str) -> bool:
    return _compatibility_report(db, client_request_id, master_request_id)['compatible']


def debug_match_report(db: Session, request_id: str, limit: int = 3) -> dict:
    source = db.execute(
        select(InkmatchRequest).where(InkmatchRequest.id == request_id)
    ).scalar_one_or_none()
    if not source:
        return {'error': 'request_not_found'}

    counterpart_role = (
        RequestCreatorRole.master
        if source.created_by_role == RequestCreatorRole.client
        else RequestCreatorRole.client
    )
    candidates = db.execute(
        select(InkmatchRequest)
        .where(
            InkmatchRequest.sketch_id == source.sketch_id,
            InkmatchRequest.created_by_role == counterpart_role,
            InkmatchRequest.created_by_user_id != source.created_by_user_id,
        )
        .order_by(InkmatchRequest.created_at.desc())
        .limit(limit)
    ).scalars().all()

    result = {
        'request_id': str(source.id),
        'sketch_id': str(source.sketch_id),
        'created_by_role': source.created_by_role.value if hasattr(source.created_by_role, 'value') else str(source.created_by_role),
        'candidate_limit': limit,
        'candidates': [],
    }

    for other in candidates:
        client_req = source if source.created_by_role == RequestCreatorRole.client else other
        master_req = source if source.created_by_role == RequestCreatorRole.master else other
        report = _compatibility_report(db, str(client_req.id), str(master_req.id))
        result['candidates'].append(
            {
                'request_id': str(other.id),
                'created_by_role': other.created_by_role.value if hasattr(other.created_by_role, 'value') else str(other.created_by_role),
                'created_by_user_id': str(other.created_by_user_id),
                'status': other.status.value if hasattr(other.status, 'value') else str(other.status),
                'created_at': other.created_at.isoformat() if other.created_at else None,
                'compatible': report['compatible'],
                'reason': report['reason'],
                'details': report['details'],
            }
        )

    return result
