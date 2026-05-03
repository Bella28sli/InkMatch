from __future__ import annotations

import json
import mimetypes
import os
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from typing import Any
from uuid import uuid4
from uuid import UUID
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from django.db import connection

PG_UUID_OIDS = {2950}
PG_BOOL_OIDS = {16}
PG_INT_OIDS = {20, 21, 23, 26, 27, 28, 29, 30, 70, 74, 80, 1016, 1082, 1182, 1184, 1266, 1700, 1790, 2202, 2203, 2204, 2205, 2206, 3734}
PG_TEXT_OIDS = {18, 19, 25, 1042, 1043, 194, 199, 1945, 3802, 114, 3807}


def _field_kind(type_code: Any) -> str:
    try:
        oid = int(type_code)
    except (TypeError, ValueError):
        return str(type_code).lower()
    if oid in PG_UUID_OIDS:
        return 'uuid'
    if oid in PG_BOOL_OIDS:
        return 'bool'
    if oid in PG_INT_OIDS:
        return 'number'
    if oid in PG_TEXT_OIDS:
        return 'text'
    return str(type_code).lower()


@dataclass
class ColumnInfo:
    name: str
    type_code: Any
    nullable: bool
    default: str | None
    primary_key: bool
    foreign_key_table: str | None = None
    foreign_key_column: str | None = None


MANUAL_ENUM_CHOICES: dict[str, list[str]] = {
    'role': ['client', 'master', 'moderator'],
    'content_type': ['sketch', 'final_work', 'process', 'portfolio', 'achievments', 'find_us', 'materials'],
    'original_author_type': ['self', 'other', 'unknown'],
    'media_type': ['image', 'video'],
    'file_type': ['image', 'video', 'document', 'other'],
    'collection_type': ['portfolio', 'materials', 'process', 'find_us', 'achievments', 'likes', 'custom'],
    'status': ['active', 'paused', 'matched', 'cancelled', 'deleted', 'draft', 'submitted', 'in_review', 'approved', 'rejected', 'closed', 'open', 'resolved'],
    'created_by_role': ['client', 'master'],
    'display_mode': ['city_only', 'street', 'metro', 'full_address'],
    'provider': ['yandex', 'dadata', 'osm', 'manual'],
    'target_type': ['moderation_action', 'user_restriction', 'complaint', 'sketch', 'message', 'comment', 'review', 'verification', 'new_post', 'message_report', 'appeal', 'suspicious_case', 'user'],
    'type': ['warn', 'block_user', 'apply_restriction', 'remove_content', 'restore_content', 'resolve_complaint'],
    'channel': ['email', 'phone'],
    'chat_kind': ['direct'],
    'document_type': ['id', 'passport', 'certificate', 'diploma', 'award', 'other'],
    'file_type': ['image', 'video', 'document', 'other'],
    'precision_level': ['exact', 'locality', 'region'],
    'workplace_type': ['studio', 'home', 'any'],
    'workplace_display_mode': ['city_only', 'street', 'metro', 'full_address'],
    'notification_type': ['message', 'inkmatch', 'session', 'moderation', 'system'],
    'entity_type': ['moderation_action', 'user_restriction', 'complaint', 'sketch', 'message', 'verification', 'appeal'],
    'status': ['open', 'in_review', 'resolved', 'rejected', 'submitted', 'approved', 'draft', 'active', 'paused', 'matched', 'cancelled', 'deleted', 'skipped', 'done'],
    'applies_to': ['general'],
}

MEDIA_FIELD_NAMES = {
    'file_url', 'image_url', 'avatar_url', 'preview_image_url', 'original_source_url', 'share_url'
}

TEXTAREA_FIELD_NAMES = {
    'bio', 'description', 'details', 'reason', 'reason_text', 'comments', 'rejection_reason',
    'decision_note', 'body', 'payload', 'context', 'text', 'public_text_override', 'title',
}


def list_tables() -> list[str]:
    with connection.cursor() as cursor:
        return connection.introspection.table_names(cursor)


def table_columns(table_name: str) -> list[ColumnInfo]:
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table_name)
        constraints = connection.introspection.get_constraints(cursor, table_name)
    primary_keys = {
        col
        for cons in constraints.values()
        if cons.get('primary_key')
        for col in cons.get('columns', [])
    }
    result: list[ColumnInfo] = []
    fk_map: dict[str, tuple[str, str]] = {}
    for cons in constraints.values():
        fk = cons.get('foreign_key')
        cols = cons.get('columns') or []
        if fk and cols:
            fk_map[cols[0]] = fk
    for column in description:
        fk_target = fk_map.get(column.name)
        result.append(
            ColumnInfo(
                name=column.name,
                type_code=getattr(column, 'type_code', None),
                nullable=bool(column.null_ok),
                default=getattr(column, 'default', None),
                primary_key=column.name in primary_keys,
                foreign_key_table=fk_target[0] if fk_target else None,
                foreign_key_column=fk_target[1] if fk_target else None,
            )
        )
    return result


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _storage_client():
    access_key = os.getenv('YANDEX_STORAGE_ACCESS_KEY_ID')
    secret_key = os.getenv('YANDEX_STORAGE_SECRET_ACCESS_KEY')
    if not access_key or not secret_key:
        raise RuntimeError('Yandex Object Storage is not configured.')
    endpoint = os.getenv('YANDEX_STORAGE_ENDPOINT') or 'https://storage.yandexcloud.net'
    return boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=os.getenv('YANDEX_STORAGE_REGION', 'ru-central1'),
        config=Config(signature_version='s3v4'),
    )


def _storage_bucket() -> str:
    bucket = os.getenv('YANDEX_STORAGE_BUCKET')
    if not bucket:
        raise RuntimeError('YANDEX_STORAGE_BUCKET is not configured.')
    return bucket


def _storage_prefix(kind: str, owner_id: str) -> str:
    root = (os.getenv('YANDEX_STORAGE_PREFIX') or 'inkmatch').strip().strip('/')
    return f'{root}/{kind}/{owner_id}'


def upload_admin_file(content: bytes, *, kind: str, owner_id: str, mime_type: str | None = None, file_name: str | None = None) -> str:
    client = _storage_client()
    bucket = _storage_bucket()
    ext = ''
    if file_name and '.' in file_name:
        ext = '.' + file_name.rsplit('.', 1)[-1]
    if not ext:
        ext = mimetypes.guess_extension(mime_type or '') or '.bin'
    key = f'{_storage_prefix(kind, owner_id)}/{uuid4().hex}{ext}'
    try:
        client.upload_fileobj(
            BytesIO(content),
            bucket,
            key,
            ExtraArgs={'ContentType': mime_type or 'application/octet-stream'},
        )
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f'Failed to upload media to Yandex Object Storage: {exc}') from exc
    return f'yandex:{key}'


def _column_lookup(table_name: str) -> dict[str, ColumnInfo]:
    return {column.name: column for column in table_columns(table_name)}


def display_column_for_table(table_name: str) -> str:
    columns = table_columns(table_name)
    for preferred in ('title', 'name', 'nickname', 'email', 'phone', 'login'):
        if any(column.name == preferred for column in columns):
            return preferred
    for column in columns:
        type_name = str(column.type_code).lower()
        if any(token in type_name for token in ('char', 'text', 'uuid')):
            return column.name
    return next((c.name for c in columns if c.primary_key), columns[0].name if columns else 'id')


def enum_choices_for_column(table_name: str, column_name: str) -> list[str]:
    if column_name in MANUAL_ENUM_CHOICES:
        return MANUAL_ENUM_CHOICES[column_name]
    with connection.cursor() as cursor:
        cursor.execute(
            f'SELECT DISTINCT CAST("{column_name}" AS TEXT) FROM "{table_name}" WHERE "{column_name}" IS NOT NULL ORDER BY 1 ASC LIMIT 200'
        )
        values = [str(row[0]) for row in cursor.fetchall() if row and row[0] is not None]
    return values


def field_display_name(column_name: str) -> str:
    parts = column_name.split('_')
    return ' '.join(part.capitalize() if part else part for part in parts)


def related_options(table_name: str, limit: int = 200) -> list[dict[str, Any]]:
    columns = table_columns(table_name)
    pk_col = next((c.name for c in columns if c.primary_key), columns[0].name if columns else 'id')
    label_col = display_column_for_table(table_name)
    with connection.cursor() as cursor:
        cursor.execute(
            f'SELECT "{pk_col}", "{label_col}" FROM "{table_name}" ORDER BY "{label_col}" ASC NULLS LAST LIMIT %s',
            [limit],
        )
        return [{'value': row[0], 'label': f'{row[1]}' if row[1] is not None else str(row[0])} for row in cursor.fetchall()]


def resolve_foreign_key_value(table_name: str, column: str, raw_value: str) -> Any:
    if raw_value == '':
        return None
    if ' — ' in raw_value:
        raw_value = raw_value.rsplit(' — ', 1)[-1].strip()
    meta = _column_lookup(table_name).get(column)
    if not meta or not meta.foreign_key_table:
        return raw_value
    target_table = meta.foreign_key_table
    target_pk = meta.foreign_key_column or next((c.name for c in table_columns(target_table) if c.primary_key), 'id')
    target_label = display_column_for_table(target_table)
    target_pk_meta = next((c for c in table_columns(target_table) if c.name == target_pk), None)
    if target_pk_meta and _field_kind(target_pk_meta.type_code) == 'uuid':
        try:
            UUID(raw_value)
        except ValueError as exc:
            raise ValueError(f'Invalid value for {column}: expected UUID or related record label') from exc
    with connection.cursor() as cursor:
        cursor.execute(
            f'SELECT "{target_pk}" FROM "{target_table}" WHERE CAST("{target_pk}" AS TEXT) = %s OR CAST("{target_label}" AS TEXT) = %s LIMIT 1',
            [raw_value, raw_value],
        )
        found = cursor.fetchone()
    if not found:
        raise ValueError(f'Invalid value for {column}: related record not found')
    return found[0]


def _coerce_filter_value(value: str, column: ColumnInfo) -> Any:
    if value == '':
        return None
    kind = _field_kind(column.type_code)
    if kind == 'bool':
        return value.lower() in {'1', 'true', 'yes', 'on'}
    if kind == 'uuid':
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValueError(f'Invalid filter for {column.name}: expected UUID') from exc
    if kind == 'number':
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                raise ValueError(f'Invalid filter for {column.name}: expected a number')
    return value


def _default_order_column(columns: list[ColumnInfo]) -> str | None:
    preferred = (
        'created_at',
        'updated_at',
        'created_on',
        'updated_on',
        'added_at',
        'occurred_at',
        'joined_at',
        'submitted_at',
        'reviewed_at',
        'confirmed_at',
    )
    for name in preferred:
        if any(column.name == name for column in columns):
            return name
    return next((c.name for c in columns if c.primary_key), columns[0].name if columns else None)


def query_rows(
    table_name: str,
    *,
    page: int = 1,
    page_size: int = 25,
    order_by: str | None = None,
    order_dir: str = 'desc',
    search: str | None = None,
    filters: dict[str, str] | None = None,
) -> tuple[list[str], list[dict[str, Any]], int]:
    columns = table_columns(table_name)
    column_map = {column.name: column for column in columns}
    where_clauses: list[str] = []
    params: list[Any] = []

    if search:
        search_clauses: list[str] = []
        for column in columns:
            kind = _field_kind(column.type_code)
            if kind in {'text', 'uuid'}:
                search_clauses.append(f'CAST({_quote_ident(column.name)} AS TEXT) ILIKE %s')
                params.append(f'%{search}%')
        if search_clauses:
            where_clauses.append('(' + ' OR '.join(search_clauses) + ')')

    for key, raw_value in (filters or {}).items():
        if raw_value is None or raw_value == '':
            continue
        column = column_map.get(key)
        if not column:
            continue
        value = _coerce_filter_value(raw_value, column)
        if value is None:
            continue
        where_clauses.append(f'{_quote_ident(key)} = %s')
        params.append(value)

    default_order_column = _default_order_column(columns)
    order_column = order_by if order_by in column_map else default_order_column
    if not order_column:
        return [], [], 0
    direction = 'ASC' if order_dir.lower() == 'asc' else 'DESC'
    if order_by not in column_map and order_column in {'created_at', 'updated_at', 'created_on', 'updated_on', 'added_at', 'occurred_at', 'joined_at', 'submitted_at', 'reviewed_at', 'confirmed_at'}:
        direction = 'DESC'

    where_sql = f'WHERE {" AND ".join(where_clauses)}' if where_clauses else ''
    count_sql = f'SELECT COUNT(*) FROM {_quote_ident(table_name)} {where_sql}'
    data_sql = (
        f'SELECT * FROM {_quote_ident(table_name)} {where_sql} '
        f'ORDER BY {_quote_ident(order_column)} {direction} NULLS LAST '
        f'LIMIT %s OFFSET %s'
    )

    with connection.cursor() as cursor:
        cursor.execute(count_sql, params)
        total = int(cursor.fetchone()[0] or 0)
        cursor.execute(data_sql, [*params, page_size, (page - 1) * page_size])
        headers = [col[0] for col in cursor.description or []]
        rows = [dict(zip(headers, row, strict=False)) for row in cursor.fetchall()]
    return headers, rows, total


def fetch_rows(table_name: str, limit: int = 100) -> tuple[list[str], list[dict[str, Any]]]:
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT * FROM "{table_name}" ORDER BY 1 DESC LIMIT %s', [limit])
        headers = [col[0] for col in cursor.description or []]
        rows = [dict(zip(headers, row, strict=False)) for row in cursor.fetchall()]
    return headers, rows


def get_row(table_name: str, pk: str) -> dict[str, Any] | None:
    cols = table_columns(table_name)
    pk_col = next((col.name for col in cols if col.primary_key), cols[0].name if cols else None)
    if not pk_col:
        return None
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT * FROM "{table_name}" WHERE "{pk_col}" = %s LIMIT 1', [pk])
        row = cursor.fetchone()
        headers = [col[0] for col in cursor.description or []]
    if not row:
        return None
    return dict(zip(headers, row, strict=False))


def _to_python(value: str, raw_type: Any) -> Any:
    if value == '':
        return None
    type_name = str(raw_type).lower()
    if 'date' in type_name and 'time' not in type_name:
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ValueError(f'Invalid date value: {value}')
    if 'timestamp' in type_name or 'datetime' in type_name or ('time' in type_name and 'date' in type_name):
        candidate = value.replace('Z', '+00:00')
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            raise ValueError(f'Invalid datetime value: {value}')
    if 'bool' in type_name:
        return value.lower() in {'1', 'true', 'yes', 'on'}
    if 'uuid' in type_name:
        try:
            return UUID(value)
        except ValueError:
            raise ValueError(f'Invalid UUID value: {value}')
    if 'int' in type_name or 'numeric' in type_name or 'decimal' in type_name or 'real' in type_name or 'double' in type_name:
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                raise ValueError(f'Invalid numeric value: {value}')
    if 'json' in type_name:
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _is_media_field(column_name: str) -> bool:
    return column_name in MEDIA_FIELD_NAMES or column_name.endswith('_url')


def save_row(table_name: str, data: dict[str, str], existing_pk: str | None = None) -> None:
    columns = table_columns(table_name)
    pk_col = next((col.name for col in columns if col.primary_key), columns[0].name if columns else None)
    if not pk_col:
        return

    payload: dict[str, Any] = {}
    for col in columns:
        if col.name == pk_col and existing_pk is None:
            continue
        if col.name not in data:
            continue
        if col.foreign_key_table:
            payload[col.name] = resolve_foreign_key_value(table_name, col.name, data[col.name])
        else:
            payload[col.name] = _to_python(data[col.name], col.type_code)

    with connection.cursor() as cursor:
        if existing_pk is None:
            if pk_col not in payload:
                pk_type = next((col.type_code for col in columns if col.name == pk_col), None)
        if _field_kind(pk_type) == 'uuid':
            payload[pk_col] = str(uuid4())
            cols = [name for name in payload.keys()]
            values = [payload[name] for name in cols]
            placeholders = ', '.join(['%s'] * len(cols))
            quoted_cols = ', '.join(f'"{col}"' for col in cols)
            cursor.execute(
                f'INSERT INTO "{table_name}" ({quoted_cols}) VALUES ({placeholders})',
                values,
            )
        else:
            assignments = ', '.join(f'"{col}" = %s' for col in payload.keys())
            values = list(payload.values()) + [existing_pk]
            cursor.execute(
                f'UPDATE "{table_name}" SET {assignments} WHERE "{pk_col}" = %s',
                values,
            )
    connection.commit()


def delete_row(table_name: str, pk: str) -> None:
    columns = table_columns(table_name)
    pk_col = next((col.name for col in columns if col.primary_key), columns[0].name if columns else None)
    if not pk_col:
        return
    with connection.cursor() as cursor:
        cursor.execute(f'DELETE FROM "{table_name}" WHERE "{pk_col}" = %s', [pk])
    connection.commit()
