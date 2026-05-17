from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Iterable

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import NotificationType
from app.models.messaging import Notification, NotificationLink, UserPushToken
from app.models.profiles import Profile


def user_nickname(db: Session, user_id: str) -> str:
    nickname = db.execute(select(Profile.nickname).where(Profile.user_id == user_id)).scalar_one_or_none()
    if nickname:
        return nickname
    return 'Пользователь'


def _push_tokens(db: Session, user_id: str) -> list[str]:
    rows = db.execute(
        select(UserPushToken).where(
            UserPushToken.user_id == user_id,
            UserPushToken.is_active.is_(True),
        )
    ).scalars().all()
    return [row.token for row in rows]


def _icon_url(name: str) -> str:
    base = (settings.media_base_url or '').rstrip('/')
    if base:
        return f'{base}/static/site/push-icons/{name}.svg'
    return f'https://inkmatch.ru/static/site/push-icons/{name}.svg'


def push_icon_url(name: str) -> str:
    return _icon_url(name)


def _normalized_text(value: str | None) -> str:
    return (value or '').strip().lower()


def _should_send_push_notification(
    *,
    type_: NotificationType,
    title: str,
    body: str,
    deep_link: str | None,
) -> bool:
    normalized_title = _normalized_text(title)
    normalized_body = _normalized_text(body)

    suppressed_titles = {
        'жалоба отправлена',
        'новая регистрация в inkmatch',
        'подтвердите email',
        'проверьте почту',
        'регистрация завершена',
    }
    if normalized_title in suppressed_titles:
        return False

    if type_ == NotificationType.system and deep_link in {'/login', '/demo-settings'}:
        return False

    if type_ == NotificationType.system and 'жалоба отправлена' in normalized_title:
        return False

    if type_ == NotificationType.system and (
        'проверьте почту' in normalized_title
        or 'подтвердите email' in normalized_title
        or 'регистрация завершена' in normalized_title
    ):
        return False

    if type_ == NotificationType.system and 'жалоба' in normalized_title and 'отправ' in normalized_body:
        return False

    return True


def _default_push_image(type_: NotificationType, title: str, body: str) -> str | None:
    normalized_title = _normalized_text(title)
    normalized_body = _normalized_text(body)

    if type_ == NotificationType.message:
        return _icon_url('message')

    if type_ == NotificationType.inkmatch:
        return _icon_url('inkmatch')

    if 'подпис' in normalized_title or 'подпис' in normalized_body:
        return _icon_url('inkmatch')

    if 'верификац' in normalized_title or 'верификац' in normalized_body:
        return _icon_url('verification')

    if 'огранич' in normalized_title or 'огранич' in normalized_body:
        return _icon_url('restriction')

    if 'жалоб' in normalized_title or 'жалоб' in normalized_body:
        return _icon_url('complaint')

    if 'модерац' in normalized_title or 'модерац' in normalized_body:
        return _icon_url('complaint')

    if 'отзыв' in normalized_title or 'отзыв' in normalized_body:
        return _icon_url('inkmatch')

    return None


def _send_push_fcm_legacy(tokens: list[str], title: str, body: str, data: dict[str, str] | None) -> None:
    if not tokens or not settings.fcm_server_key:
        return

    payload = {
        'registration_ids': tokens,
        'notification': {'title': title, 'body': body},
        'data': data or {},
        'priority': 'high',
    }

    req = urllib.request.Request(
        'https://fcm.googleapis.com/fcm/send',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'key={settings.fcm_server_key}',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            response.read()
    except urllib.error.URLError:
        return


def _fcm_v1_access_token() -> str | None:
    creds_path = settings.google_application_credentials
    if not creds_path:
        return None

    absolute_path = creds_path
    if not os.path.isabs(absolute_path):
        absolute_path = os.path.join(os.getcwd(), creds_path)

    if not os.path.exists(absolute_path):
        return None

    try:
        credentials = service_account.Credentials.from_service_account_file(
            absolute_path,
            scopes=['https://www.googleapis.com/auth/firebase.messaging'],
        )
        credentials.refresh(Request())
        return credentials.token
    except Exception:
        return None


def _send_push_fcm_v1(
    type_: NotificationType,
    tokens: list[str],
    title: str,
    body: str,
    data: dict[str, str] | None,
    image_url: str | None,
) -> None:
    project_id = settings.firebase_project_id
    if not tokens or not project_id:
        return

    access_token = _fcm_v1_access_token()
    if not access_token:
        return

    endpoint = f'https://fcm.googleapis.com/v1/projects/{project_id}/messages:send'
    for device_token in tokens:
        message_payload = {
            'token': device_token,
            'data': {
                **(data or {}),
                'notification_type': type_.value,
                'push_title': title,
                'push_body': body,
            },
        }
        if type_ != NotificationType.message:
            message_payload['notification'] = {
                'title': title,
                'body': body,
                **({'image': image_url} if image_url else {}),
            }
        payload = {
            'message': message_payload
        }
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Content-Type': 'application/json; UTF-8',
                'Authorization': f'Bearer {access_token}',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                response.read()
        except urllib.error.URLError:
            continue


def send_push(
    db: Session,
    *,
    user_id: str,
    type_: NotificationType,
    title: str,
    body: str,
    deep_link: str | None = None,
    image_url: str | None = None,
    extra_data: dict[str, str] | None = None,
) -> None:
    tokens = _push_tokens(db, user_id)
    if not tokens:
        return

    data = dict(extra_data or {})
    if deep_link:
        data['deep_link'] = deep_link
    effective_image_url = image_url or _default_push_image(type_, title, body)

    provider = (settings.push_provider or 'log').lower()
    if provider == 'fcm_v1':
        _send_push_fcm_v1(type_, tokens, title, body, data, effective_image_url)
    elif provider == 'fcm':
        _send_push_fcm_legacy(tokens, title, body, data)
    else:
        print(f'[push] user={user_id} title={title} body={body} deep_link={deep_link} tokens={len(tokens)}')


def create_notification(
    db: Session,
    *,
    user_id: str,
    type_: NotificationType,
    title: str,
    body: str,
    deep_link: str | None = None,
    image_url: str | None = None,
    links: Iterable[tuple[str, str]] | None = None,
    send_push_too: bool = True,
    in_app: bool = True,
) -> Notification | None:
    created: Notification | None = None
    if in_app:
        created = Notification(
            user_id=user_id,
            type=type_,
            title=title,
            body=body,
            image_url=image_url,
            deep_link=deep_link,
        )
        db.add(created)
        db.flush()

        if links:
            for entity_type, entity_id in links:
                db.add(
                    NotificationLink(
                        notification_id=created.id,
                        entity_type=entity_type,
                        entity_id=entity_id,
                    )
                )

    if send_push_too:
        if _should_send_push_notification(
            type_=type_,
            title=title,
            body=body,
            deep_link=deep_link,
        ):
            send_push(
                db,
                user_id=user_id,
                type_=type_,
                title=title,
                body=body,
                deep_link=deep_link,
                image_url=image_url,
            )

    return created


def register_push_token(db: Session, *, user_id: str, platform: str, token: str) -> None:
    existing = db.execute(select(UserPushToken).where(UserPushToken.token == token)).scalar_one_or_none()
    if existing:
        existing.user_id = user_id
        existing.platform = platform
        existing.is_active = True
        db.commit()
        return

    db.add(UserPushToken(user_id=user_id, platform=platform, token=token, is_active=True))
    db.commit()


def deactivate_push_token(db: Session, *, user_id: str, token: str) -> None:
    row = db.execute(
        select(UserPushToken).where(
            UserPushToken.user_id == user_id,
            UserPushToken.token == token,
        )
    ).scalar_one_or_none()
    if not row:
        return
    row.is_active = False
    db.commit()
