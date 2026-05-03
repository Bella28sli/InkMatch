from __future__ import annotations

import mimetypes
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings

YANDEX_PREFIX = 'yandex:'


def _storage_client():
    if not settings.yandex_storage_access_key_id or not settings.yandex_storage_secret_access_key:
        raise RuntimeError('Yandex Object Storage is not configured.')
    endpoint = settings.yandex_storage_endpoint or f'https://storage.yandexcloud.net'
    return boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=settings.yandex_storage_access_key_id,
        aws_secret_access_key=settings.yandex_storage_secret_access_key,
        region_name=settings.yandex_storage_region,
        config=Config(signature_version='s3v4'),
    )


def _bucket() -> str:
    if not settings.yandex_storage_bucket:
        raise RuntimeError('YANDEX_STORAGE_BUCKET is not configured.')
    return settings.yandex_storage_bucket


def _prefix(kind: str, owner_id: str) -> str:
    root = (settings.yandex_storage_prefix or 'inkmatch').strip().strip('/')
    return f'{root}/{kind}/{owner_id}'


def _object_key(kind: str, owner_id: str, mime_type: str | None = None) -> str:
    ext = mimetypes.guess_extension(mime_type or '') or '.bin'
    return f'{_prefix(kind, owner_id)}/{uuid4().hex}{ext}'


def _object_key_with_hint(kind: str, owner_id: str, *, mime_type: str | None = None, file_ext: str | None = None) -> str:
    ext = ''
    if file_ext:
        ext = file_ext if file_ext.startswith('.') else f'.{file_ext}'
    if not ext and mime_type:
        ext = mimetypes.guess_extension(mime_type or '') or ''
    if not ext:
        ext = '.bin'
    return f'{_prefix(kind, owner_id)}/{uuid4().hex}{ext}'


def _public_base_url() -> str:
    if settings.yandex_storage_public_base_url:
        return settings.yandex_storage_public_base_url.rstrip('/')
    bucket = _bucket()
    return f'https://{bucket}.storage.yandexcloud.net'


def _normalize_object_key(value: str) -> str | None:
    if not value:
        return None
    if value.startswith(YANDEX_PREFIX):
        return value[len(YANDEX_PREFIX):]
    if value.startswith('http://') or value.startswith('https://'):
        parsed = urlparse(value)
        if parsed.netloc.endswith('storage.yandexcloud.net'):
            return parsed.path.lstrip('/')
    return value


def upload_media(
    content: bytes,
    kind: str,
    owner_id: str,
    mime_type: str | None = None,
    file_ext: str | None = None,
) -> str:
    client = _storage_client()
    bucket = _bucket()
    key = _object_key_with_hint(kind, owner_id, mime_type=mime_type, file_ext=file_ext)
    extra_args: dict[str, Any] = {'ContentType': mime_type or 'application/octet-stream'}
    try:
        client.upload_fileobj(BytesIO(content), bucket, key, ExtraArgs=extra_args)
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f'Failed to upload media to Yandex Object Storage: {exc}') from exc
    return f'{YANDEX_PREFIX}{key}'


def normalize_media_reference(value: str) -> str:
    if not value:
        return value
    if value.startswith(YANDEX_PREFIX):
        return value
    key = _normalize_object_key(value)
    if key:
        return f'{YANDEX_PREFIX}{key}'
    return value


def resolve_media_url(value: str | None) -> str | None:
    if not value:
        return value
    key = _normalize_object_key(value)
    if not key:
        return value

    if settings.yandex_storage_use_presigned_urls:
        client = _storage_client()
        try:
            return client.generate_presigned_url(
                'get_object',
                Params={'Bucket': _bucket(), 'Key': key},
                ExpiresIn=settings.yandex_storage_presigned_url_ttl_seconds,
            )
        except (BotoCoreError, ClientError):
            return None

    return f'{_public_base_url()}/{key}'


def delete_media_reference(value: str | None) -> bool:
    key = _normalize_object_key(value or '')
    if not key:
        return False
    client = _storage_client()
    try:
        client.delete_object(Bucket=_bucket(), Key=key)
        return True
    except (BotoCoreError, ClientError):
        return False
