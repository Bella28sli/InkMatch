from __future__ import annotations

import base64
from email.message import EmailMessage
from email.header import Header
from html import escape
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from app.core.config import settings


class EmailServiceError(Exception):
    pass


GMAIL_SEND_SCOPE = 'https://www.googleapis.com/auth/gmail.send'
GMAIL_SEND_ENDPOINT = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send'


def _load_credentials() -> Credentials:
    token_path = Path(settings.gmail_token_path)
    if not token_path.exists():
        raise EmailServiceError(f'Gmail token file not found: {token_path}')

    creds = Credentials.from_authorized_user_file(str(token_path), [GMAIL_SEND_SCOPE])
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as exc:
            raise EmailServiceError(f'Failed to refresh Gmail token: {exc}') from exc
        token_path.write_text(creds.to_json(), encoding='utf-8')
    if not creds.valid or not creds.token:
        raise EmailServiceError('Gmail credentials are not valid')
    return creds


def _build_message(subject: str, body: str, recipient: str) -> str:
    message = EmailMessage()
    message['To'] = recipient
    message['Subject'] = str(Header(subject, 'utf-8'))
    message.set_content(body, charset='utf-8')
    message.add_alternative(
        '<html><body style="font-family: Arial, sans-serif; line-height: 1.6;">'
        f'<div style="white-space: pre-wrap;">{escape(body)}</div>'
        '</body></html>',
        subtype='html',
    )
    return base64.urlsafe_b64encode(message.as_bytes()).decode('ascii')


def send_email(subject: str, body: str, recipient: str) -> None:
    creds = _load_credentials()
    raw_message = _build_message(subject, body, recipient)
    try:
        response = requests.post(
            GMAIL_SEND_ENDPOINT,
            headers={'Authorization': f'Bearer {creds.token}'},
            json={'raw': raw_message},
            timeout=20,
        )
    except Exception as exc:
        raise EmailServiceError(f'Failed to send email via Gmail API: {exc}') from exc

    if response.status_code >= 400:
        raise EmailServiceError(
            f'Gmail API rejected the message: {response.status_code} {response.text[:300]}'
        )


def send_verification_email(recipient: str, code: str) -> None:
    send_email(
        'InkMatch - подтверждение регистрации',
        (
            'Здравствуйте!\n\n'
            f'Ваш код подтверждения: {code}\n\n'
            'Введите его в приложении InkMatch, чтобы подтвердить email.\n'
            'Если вы не регистриовались, просто проигнорируйте это письмо.\n'
        ),
        recipient,
    )


def send_password_reset_email(recipient: str, code: str) -> None:
    send_email(
        'InkMatch - сброс пароля',
        (
            'Здравствуйте!\n\n'
            f'Ваш код для сброса пароля: {code}\n\n'
            'Введите его в приложении InkMatch, чтобы продолжить сброс пароля.\n'
            'Если вы не запрашивали сброс пароля, просто проигнорируйте это письмо.\n'
        ),
        recipient,
    )
