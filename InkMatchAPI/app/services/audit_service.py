from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import AuditSource
from app.models.moderation import AuditEvent, AuditEventTarget


API_SKIP_PATHS = {'/docs', '/redoc', '/openapi.json'}


def should_skip_path(path: str) -> bool:
    return path in API_SKIP_PATHS


def resolve_source(headers: Any) -> AuditSource:
    source_header = (headers.get('x-client-source') or '').lower().strip()
    if source_header in {AuditSource.mobile.value, AuditSource.web.value, AuditSource.admin.value, AuditSource.system.value}:
        return AuditSource(source_header)

    user_agent = (headers.get('user-agent') or '').lower()
    if 'flutter' in user_agent or 'dart' in user_agent or 'okhttp' in user_agent:
        return AuditSource.mobile
    if 'mozilla' in user_agent or 'chrome' in user_agent or 'safari' in user_agent:
        return AuditSource.web
    return AuditSource.system


def extract_actor_from_token(auth_header: str | None) -> tuple[UUID | None, str | None]:
    if not auth_header:
        return None, None

    prefix = 'bearer '
    if not auth_header.lower().startswith(prefix):
        return None, None

    token = auth_header[len(prefix):].strip()
    if not token:
        return None, None

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={'verify_exp': False},
        )
    except JWTError:
        return None, None

    user_id = payload.get('sub')
    role = payload.get('role')

    actor_id = None
    if user_id:
        try:
            actor_id = UUID(str(user_id))
        except ValueError:
            actor_id = None

    actor_role = str(role) if role is not None else None
    return actor_id, actor_role


def build_event_type(method: str, endpoint_name: str | None) -> str:
    if endpoint_name:
        value = f'{method.lower()}.{endpoint_name.lower()}'
    else:
        value = method.lower()
    return value[:64]


def hash_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    salted = f'{settings.jwt_secret_key}:{ip}'
    return hashlib.sha256(salted.encode('utf-8')).hexdigest()


TARGET_TYPE_BY_PARAM = {
    'user_id': 'user',
    'target_user_id': 'user',
    'owner_id': 'user',
    'post_id': 'sketch',
    'sketch_id': 'sketch',
    'comment_id': 'comment',
    'message_id': 'message',
    'chat_id': 'chat',
    'collection_id': 'collection',
    'complaint_id': 'complaint',
    'queue_id': 'moderation_queue',
    'restriction_id': 'user_restriction',
    'appeal_id': 'appeal',
    'reason_id': 'moderation_reason',
    'warning_id': 'warning',
    'review_id': 'inkmatch_review',
    'request_id': 'request',
    'workplace_id': 'workplace',
    'location_id': 'location',
    'station_id': 'metro_station',
}


def _iter_body_targets(value: Any) -> list[tuple[str, Any]]:
    pairs: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        target_type = value.get('target_type')
        target_id = value.get('target_id')
        if target_type and target_id:
            pairs.append((str(target_type), target_id))
        for key, item in value.items():
            if key in TARGET_TYPE_BY_PARAM or key.endswith('_id'):
                pairs.append((key, item))
            pairs.extend(_iter_body_targets(item))
    elif isinstance(value, list):
        for item in value:
            pairs.extend(_iter_body_targets(item))
    return pairs


def parse_target_uuids(
    path_params: dict[str, Any],
    query_params: dict[str, Any] | None = None,
    body_params: dict[str, Any] | list[Any] | None = None,
) -> list[tuple[str, UUID]]:
    targets: list[tuple[str, UUID]] = []
    seen: set[tuple[str, UUID]] = set()
    merged = {**(query_params or {}), **path_params}
    pairs: list[tuple[str, Any]] = list(merged.items())
    if body_params is not None:
        pairs.extend(_iter_body_targets(body_params))

    for key, raw in pairs:
        if raw is None:
            continue
        try:
            value = UUID(str(raw))
        except ValueError:
            continue
        target_type = TARGET_TYPE_BY_PARAM.get(key, key.removesuffix('_id'))[:32]
        marker = (target_type, value)
        if marker in seen:
            continue
        seen.add(marker)
        targets.append(marker)
    return targets


def log_audit_event(
    db: Session,
    *,
    method: str,
    path: str,
    endpoint_name: str | None,
    status_code: int,
    duration_ms: int,
    source: AuditSource,
    auth_header: str | None,
    client_ip: str | None,
    path_params: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    body_params: dict[str, Any] | list[Any] | None = None,
) -> None:
    actor_user_id, actor_role = extract_actor_from_token(auth_header)

    event = AuditEvent(
        occurred_at=datetime.now(timezone.utc),
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        event_type=build_event_type(method, endpoint_name),
        source=source,
        ip_hash=hash_ip(client_ip),
        context={
            'method': method,
            'path': path,
            'status_code': status_code,
            'duration_ms': duration_ms,
            'query': query_params or {},
            'body_targets': [
                {'key': key, 'value': str(value)}
                for key, value in _iter_body_targets(body_params or {})
            ][:30],
        },
    )
    db.add(event)
    db.flush()

    for target_type, target_id in parse_target_uuids(path_params or {}, query_params, body_params):
        db.add(
            AuditEventTarget(
                audit_event_id=event.id,
                target_type=target_type,
                target_id=target_id,
            )
        )

    db.commit()
