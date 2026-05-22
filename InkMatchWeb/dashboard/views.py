from __future__ import annotations

from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from urllib.parse import urlencode

from .utils import (
    _default_order_column,
    delete_row,
    enum_choices_for_column,
    fetch_rows,
    field_display_name,
    get_row,
    list_tables,
    query_rows,
    related_options,
    save_row,
    table_columns,
    upload_admin_file,
)


TABLE_DESCRIPTIONS = {
    'users': 'Учетные записи пользователей, контакты, роль и статус активности.',
    'profiles': 'Публичные профили: никнейм, аватар, био и базовые настройки.',
    'master_profiles': 'Параметры мастеров: опыт, цены, рейтинг и подтверждение.',
    'inkmatch_defaults': 'Базовые настройки InkMatch: поиск, радиус, город и предпочтения.',
    'subscriptions': 'Подписки между пользователями.',
    'refresh_tokens': 'Токены обновления авторизации.',
    'verification_codes': 'Коды подтверждения по email и телефону.',
    'sketches': 'Посты-эскизы: автор, тип контента, видимость и описание.',
    'sketch_media': 'Медиафайлы постов: ссылки, хеши, порядок и типы файлов.',
    'sketch_comments': 'Комментарии к скетчам, включая ответы и связь с автором.',
    'comments_attachments': 'Вложения к комментариям.',
    'sketch_styles': 'Связь скетчей со стилями.',
    'sketch_tags': 'Связь скетчей с тегами.',
    'tags': 'Справочник тегов для скетчей и поиска.',
    'styles': 'Справочник стилей татуировки.',
    'collections': 'Коллекции пользователя: портфолио, процесс, материалы и прочее.',
    'collection_items': 'Элементы коллекций и метаданные работы: цена, длительность, валюта и заметка.',
    'sketch_comment_likes': 'Лайки комментариев.',
    'sketch_pins': 'Закрепленные комментарии и заметки для постов.',
    'sketch_likes': 'Лайки постов.',
    'feed_preferred_tags': 'Предпочтительные теги для ленты.',
    'feed_preferred_styles': 'Предпочтительные стили для ленты.',
    'chats': 'Чаты между пользователями и связанная карточка диалога.',
    'chat_participants': 'Участники чатов.',
    'messages': 'Сообщения в чатах: текст, вложения и статус прочтения.',
    'message_reads': 'Отметки о прочтении сообщений.',
    'message_attachments': 'Вложения в сообщениях.',
    'notifications': 'Уведомления пользователя с заголовком, текстом и ссылкой.',
    'notification_links': 'Ссылки уведомлений на связанные сущности.',
    'user_push_tokens': 'Токены push-уведомлений устройств.',
    'inkmatch_requests': 'Заявки InkMatch между клиентом и мастером.',
    'client_inkmatch_params': 'Параметры поиска клиента для InkMatch-заявок.',
    'master_inkmatch_offer': 'Предложения мастеров по InkMatch-заявкам.',
    'inkmatches': 'Состоявшиеся InkMatch-сопоставления и их статус.',
    'inkmatch_reviews': 'Отзывы по InkMatch-сессиям.',
    'inkmatch_review_attachments': 'Вложения к отзывам InkMatch.',
    'locations': 'Города, регионы и адресные точки.',
    'metro_stations': 'Станции метро и привязка к городу.',
    'master_workplaces': 'Рабочие места и студии мастеров.',
    'moderation_reasons': 'Справочник причин для модерации, предупреждений и ограничений.',
    'user_warnings': 'История предупреждений пользователей и их статус.',
    'moderation_queue_items': 'Очередь модерации по всем объектам.',
    'complaints': 'Жалобы пользователей на контент, сообщения и профили.',
    'appeals': 'Апелляции пользователей на ограничения и решения модерации.',
    'appeal_attachments': 'Файлы, прикрепленные к апелляциям.',
    'moderation_actions': 'Действия модераторов по жалобам, ограничениям и контенту.',
    'audit_events': 'Журнал аудита по событиям API и админки.',
    'audit_event_targets': 'Привязки audit-событий к конкретным сущностям.',
    'user_restrictions': 'Ограничения, блокировки и скрытия пользователей.',
}

TABLE_FIELD_LABELS = {
    'users': {
        'password_hash': 'Пароль',
        'role': 'Роль',
        'email': 'Email',
        'phone': 'Телефон',
        'is_verified': 'Подтвержден',
    },
    'profiles': {
        'nickname': 'Никнейм',
        'avatar_url': 'Аватар',
        'bio': 'О себе',
        'home_location_id': 'Домашняя локация',
        'default_currency': 'Валюта',
    },
    'master_profiles': {
        'experience_years': 'Опыт, лет',
        'price_min': 'Цена от',
        'price_max': 'Цена до',
        'description': 'Описание',
        'is_verified': 'Проверен',
        'is_favorite': 'В избранном',
        'verification_skipped': 'Верификация пропущена',
        'rating_avg': 'Средний рейтинг',
        'completed_sessions_count': 'Завершённых сессий',
    },
    'sketches': {
        'author_id': 'Автор',
        'content_type': 'Тип контента',
        'feed_visibility': 'Видимость',
        'title': 'Заголовок',
        'description': 'Описание',
        'original_author_type': 'Тип оригинального автора',
        'original_author_name': 'Имя оригинального автора',
        'original_source_url': 'Источник',
        'original_author_user_id': 'Пользователь-автор',
        'like_amount': 'Лайки',
        'reviewed': 'Проверено',
    },
    'sketch_media': {
        'sketch_id': 'Скетч',
        'media_type': 'Тип медиа',
        'url': 'Файл',
        'preview_image_url': 'Превью',
        'duration_seconds': 'Длительность, сек',
        'width': 'Ширина',
        'height': 'Высота',
        'file_size_bytes': 'Размер, байт',
        'sha256': 'SHA256',
        'phash': 'Phash',
        'sort_order': 'Порядок',
    },
    'collections': {
        'owner_id': 'Владелец',
        'collection_type': 'Тип коллекции',
        'title': 'Название',
        'description': 'Описание',
        'is_system': 'Системная',
        'is_private': 'Приватная',
    },
    'collection_items': {
        'collection_id': 'Коллекция',
        'sketch_id': 'Скетч',
        'sort_order': 'Порядок',
        'work_duration_houres': 'Длительность, часы',
        'work_price': 'Цена',
        'currency': 'Валюта',
        'note': 'Заметка',
    },
    'locations': {
        'country': 'Страна',
        'region': 'Регион',
        'locality': 'Город',
        'address_line': 'Адрес',
        'entrance': 'Подъезд',
        'postal_code': 'Индекс',
        'lat': 'Широта',
        'lon': 'Долгота',
        'precision_level': 'Точность',
        'provider': 'Провайдер',
        'provider_place_id': 'ID места',
    },
    'metro_stations': {
        'city_location_id': 'Город',
        'name': 'Название',
        'line_name': 'Линия',
        'lat': 'Широта',
        'lon': 'Долгота',
        'color_hex': 'Цвет',
    },
    'master_workplaces': {
        'master_id': 'Мастер',
        'location_id': 'Локация',
        'is_home_studio': 'Домашняя студия',
        'studio_name': 'Название студии',
        'public_display_mode': 'Показывать как',
        'public_metro_station_id': 'Станция метро',
        'public_text_override': 'Публичный текст',
        'show_on_map': 'Показывать на карте',
        'public_lat': 'Публичная широта',
        'public_lon': 'Публичная долгота',
        'is_primary': 'Основное место',
    },
    'moderation_reasons': {
        'code': 'Код',
        'title': 'Название',
        'description': 'Описание',
        'applies_to': 'Для чего',
        'priority': 'Приоритет',
        'is_active': 'Активно',
    },
    'user_warnings': {
        'user_id': 'Пользователь',
        'issued_by_moderator_id': 'Модератор',
        'reason_id': 'Причина',
        'reason_text': 'Текст причины',
        'status': 'Статус',
        'related_restriction_id': 'Связанное ограничение',
    },
    'moderation_queue_items': {
        'entity_type': 'Тип сущности',
        'entity_id': 'ID сущности',
        'priority': 'Приоритет',
        'status': 'Статус',
        'assigned_moderator_id': 'Модератор',
    },
    'complaints': {
        'author_id': 'Автор',
        'target_type': 'Тип цели',
        'target_id': 'ID цели',
        'reason': 'Причина',
        'details': 'Детали',
        'status': 'Статус',
    },
    'appeals': {
        'appellant_user_id': 'Заявитель',
        'target_type': 'Тип цели',
        'target_id': 'ID цели',
        'description': 'Описание',
        'status': 'Статус',
        'reason_text': 'Текст причины',
        'reviewed_by_moderator_id': 'Модератор',
        'decision_note': 'Комментарий решения',
    },
    'appeal_attachments': {
        'appeal_id': 'Апелляция',
        'file_url': 'Файл',
        'file_type': 'Тип файла',
    },
    'moderation_actions': {
        'moderator_id': 'Модератор',
        'action_type': 'Действие',
        'target_type': 'Тип цели',
        'target_id': 'ID цели',
        'complaint_id': 'Жалоба',
        'reason': 'Причина',
        'params': 'Параметры',
    },
    'audit_events': {
        'occurred_at': 'Когда',
        'actor_user_id': 'Пользователь',
        'actor_role': 'Роль',
        'event_type': 'Событие',
        'source': 'Источник',
        'ip_hash': 'IP hash',
        'context': 'Контекст',
    },
    'notifications': {
        'user_id': 'Пользователь',
        'type': 'Тип',
        'title': 'Заголовок',
        'body': 'Текст',
        'is_read': 'Прочитано',
        'image_url': 'Изображение',
        'deep_link': 'Ссылка',
    },
    'message_attachments': {
        'message_id': 'Сообщение',
        'file_url': 'Файл',
        'file_type': 'Тип файла',
        'mime_type': 'MIME',
        'file_size_bytes': 'Размер, байт',
    },
    'messages': {
        'chat_id': 'Чат',
        'sender_id': 'Отправитель',
        'message_type': 'Тип сообщения',
        'text': 'Текст',
        'payload': 'Данные',
    },
    'chats': {
        'chat_kind': 'Тип чата',
        'created_by_user_id': 'Создан пользователем',
    },
    'chat_participants': {
        'chat_id': 'Чат',
        'user_id': 'Пользователь',
    },
    'master_verification_requests': {
        'master_id': 'Мастер',
        'status': 'Статус',
        'comments': 'Комментарии',
        'rejection_reason': 'Причина отказа',
    },
    'master_verification_personal_data': {
        'first_name': 'Имя',
        'second_name': 'Второе имя',
        'last_name': 'Фамилия',
        'patronymic': 'Отчество',
        'birth_date': 'Дата рождения',
        'citizenship': 'Гражданство',
    },
    'master_verification_documents': {
        'request_id': 'Заявка',
        'document_type': 'Тип документа',
        'title': 'Название',
        'issuer': 'Кем выдан',
        'issued_date': 'Дата выдачи',
    },
    'master_verification_document_files': {
        'document_id': 'Документ',
        'file_url': 'Файл',
        'file_type': 'Тип файла',
    },
}

HIDDEN_COLUMN_PREFIXES = ('original_author_',)
BACKUP_DIRS = (
    Path('/root'),
    Path('/tmp'),
    Path('/opt/inkmatch/backups'),
)


def landing(request: HttpRequest) -> HttpResponse:
    apk_url = request.build_absolute_uri('/static/downloads/InkMatch.apk')
    highlights = [
        'Стиль и локация',
        'От интереса к диалогу',
        'Лента и заявки',
        'Без лишнего шума',
    ]
    return render(
        request,
        'landing.html',
        {
            'highlights': highlights,
            'apk_url': apk_url,
        },
    )


@login_required
def index(request: HttpRequest) -> HttpResponse:
    tables = list_tables()
    groups = [
        {
            'title': 'Модерация и безопасность',
            'count': sum(1 for t in tables if t in {
                'moderation_reasons', 'user_warnings', 'moderation_queue_items', 'complaints',
                'appeals', 'appeal_attachments', 'moderation_actions', 'audit_events',
                'audit_event_targets', 'user_restrictions',
            }),
            'link': reverse('table-list'),
            'description': 'Жалобы, предупреждения, очередь модерации и аудит.',
        },
        {
            'title': 'Пользователи и профили',
            'count': sum(1 for t in tables if t in {
                'users', 'profiles', 'master_profiles', 'inkmatch_defaults', 'subscriptions',
                'refresh_tokens', 'verification_codes',
            }),
            'link': reverse('table-list'),
            'description': 'Аккаунты, профили, роли и параметры входа.',
        },
        {
            'title': 'Скетчи и коллекции',
            'count': sum(1 for t in tables if t in {
                'sketches', 'sketch_media', 'sketch_comments', 'comments_attachments',
                'sketch_styles', 'sketch_tags', 'tags', 'styles', 'collections', 'collection_items',
                'sketch_comment_likes', 'sketch_pins', 'sketch_likes', 'feed_preferred_tags', 'feed_preferred_styles',
            }),
            'link': reverse('table-list'),
            'description': 'Контент ленты, теги, стили и коллекции.',
        },
        {
            'title': 'Сообщения и уведомления',
            'count': sum(1 for t in tables if t in {
                'chats', 'chat_participants', 'messages', 'message_reads', 'message_attachments',
                'notifications', 'notification_links', 'user_push_tokens',
            }),
            'link': reverse('table-list'),
            'description': 'Чаты, сообщения, пуши и статусы прочтения.',
        },
        {
            'title': 'InkMatch и справочники',
            'count': sum(1 for t in tables if t in {
                'inkmatch_requests', 'client_inkmatch_params', 'master_inkmatch_offer', 'inkmatches',
                'inkmatch_reviews', 'inkmatch_review_attachments', 'locations', 'metro_stations',
                'master_workplaces',
            }),
            'link': reverse('table-list'),
            'description': 'Заявки, сессии, локации и метро.',
        },
    ]
    return render(
        request,
        'dashboard/index.html',
        {'tables': tables, 'groups': groups, 'backups': list_backups()},
    )


def _restore_command_for(path: Path) -> str:
    if path.name.endswith('.sql'):
        return f"sudo -u postgres psql inkmatch < {path}"
    if path.name.endswith(('.tar.gz', '.tgz')):
        return f"tar -xzf {path} -C /tmp/inkmatch_restore"
    if path.name.endswith('.zip'):
        return f"unzip {path} -d /tmp/inkmatch_restore"
    return str(path)


def list_backups() -> list[dict[str, str]]:
    found: dict[str, Path] = {}
    patterns = ('*.sql', '*.tar.gz', '*.tgz', '*.zip')
    for base_dir in BACKUP_DIRS:
        if not base_dir.exists():
            continue
        for pattern in patterns:
            for path in base_dir.rglob(pattern):
                if path.is_file():
                    found.setdefault(path.name, path)
    backups = []
    for name, path in sorted(found.items(), key=lambda item: item[0].lower()):
        backups.append(
            {
                'name': name,
                'path': str(path),
                'download_url': reverse('backup-download', kwargs={'backup_name': name}),
                'restore_command': _restore_command_for(path),
            }
        )
    return backups


@login_required
def backups(request: HttpRequest) -> HttpResponse:
    return render(request, 'dashboard/backups.html', {'backups': list_backups()})


@login_required
def backup_download(request: HttpRequest, backup_name: str) -> HttpResponse:
    for base_dir in BACKUP_DIRS:
        if not base_dir.exists():
            continue
        for path in base_dir.rglob(backup_name):
            if path.is_file():
                return FileResponse(open(path, 'rb'), as_attachment=True, filename=path.name)
    raise Http404('Backup not found')


@login_required
def table_list(request: HttpRequest) -> HttpResponse:
    tables = list_tables()
    groups = [
        {
            'title': 'Модерация и безопасность',
            'tables': [t for t in tables if t in {
                'moderation_reasons', 'user_warnings', 'moderation_queue_items', 'complaints',
                'appeals', 'appeal_attachments', 'moderation_actions', 'audit_events',
                'audit_event_targets', 'user_restrictions',
            }],
        },
        {
            'title': 'Пользователи и профили',
            'tables': [t for t in tables if t in {
                'users', 'profiles', 'master_profiles', 'inkmatch_defaults', 'subscriptions',
                'refresh_tokens', 'verification_codes',
            }],
        },
        {
            'title': 'Скетчи и коллекции',
            'tables': [t for t in tables if t in {
                'sketches', 'sketch_media', 'sketch_comments', 'comments_attachments',
                'sketch_styles', 'sketch_tags', 'tags', 'styles', 'collections', 'collection_items',
                'sketch_comment_likes', 'sketch_pins', 'sketch_likes', 'feed_preferred_tags', 'feed_preferred_styles',
            }],
        },
        {
            'title': 'Сообщения и уведомления',
            'tables': [t for t in tables if t in {
                'chats', 'chat_participants', 'messages', 'message_reads', 'message_attachments',
                'notifications', 'notification_links', 'user_push_tokens',
            }],
        },
        {
            'title': 'InkMatch и справочники',
            'tables': [t for t in tables if t in {
                'inkmatch_requests', 'client_inkmatch_params', 'master_inkmatch_offer', 'inkmatches',
                'inkmatch_reviews', 'inkmatch_review_attachments', 'locations', 'metro_stations',
                'master_workplaces',
            }],
        },
    ]
    used = {name for group in groups for name in group['tables']}
    extra = [t for t in tables if t not in used]
    if extra:
        groups.append({'title': 'Прочее', 'tables': extra})
    for group in groups:
        group['items'] = [
            {
                'name': table,
                'description': TABLE_DESCRIPTIONS.get(table, 'Техническая таблица проекта InkMatch.'),
            }
            for table in group['tables']
        ]
    return render(request, 'dashboard/table_list.html', {'tables': tables, 'groups': groups})


@login_required
def table_detail(request: HttpRequest, table_name: str) -> HttpResponse:
    if table_name not in list_tables():
        raise Http404('Table not found')
    columns = table_columns(table_name)
    visible_columns = [column for column in columns if not column.name.startswith(HIDDEN_COLUMN_PREFIXES)]
    pk_col = next((c.name for c in columns if c.primary_key), columns[0].name if columns else None)
    default_order = _default_order_column(columns)
    page = max(int(request.GET.get('page', '1') or 1), 1)
    page_size = min(max(int(request.GET.get('page_size', '25') or 25), 5), 100)
    order_by = request.GET.get('sort') or default_order or pk_col
    order_dir = request.GET.get('dir', 'desc')
    search = (request.GET.get('q') or '').strip() or None
    filters = {column.name: request.GET.get(f'f_{column.name}', '').strip() for column in visible_columns}
    error_message = None
    try:
        headers, rows, total = query_rows(
            table_name,
            page=page,
            page_size=page_size,
            order_by=order_by,
            order_dir=order_dir,
            search=search,
            filters=filters,
        )
    except ValueError as exc:
        headers, rows, total = [], [], 0
        error_message = str(exc)
        messages.error(request, error_message)
    total_pages = max((total + page_size - 1) // page_size, 1)
    base_params = {}
    for key, value in request.GET.items():
        if key in {'page', 'sort', 'dir'}:
            continue
        if value:
            base_params[key] = value
    query_base = urlencode(base_params)
    if query_base:
        query_base = f'{query_base}&'
    current_query = request.GET.urlencode()
    current_path = request.get_full_path()
    return render(
        request,
        'dashboard/table_detail.html',
        {
            'table_name': table_name,
            'columns': visible_columns,
            'headers': [header for header in headers if not header.startswith(HIDDEN_COLUMN_PREFIXES)],
            'rows': rows,
            'pk_col': pk_col,
            'page': page,
            'page_size': page_size,
            'page_sizes': [10, 25, 50, 100],
            'total': total,
            'total_pages': total_pages,
            'sort': order_by,
            'selected_sort': order_by if order_by in {column.name for column in visible_columns} else pk_col,
            'dir': order_dir if order_dir in {'asc', 'desc'} else 'desc',
            'q': search or '',
            'filters': filters,
            'query_base': query_base,
            'current_query': current_query,
            'current_path': current_path,
            'error_message': error_message,
            'table_grid_columns': f'44px repeat({len(headers)}, minmax(160px, max-content)) 180px',
        },
    )


def _form_payload(request: HttpRequest, table_name: str) -> dict[str, str]:
    columns = table_columns(table_name)
    return {col.name: request.POST.get(col.name, '') for col in columns}


def _normalize_next_url(next_url: str | None, table_name: str) -> str:
    if not next_url:
        return reverse('table-detail', args=[table_name])
    if next_url.startswith(('http://', 'https://', '/', '?')):
        return next_url
    if '=' in next_url or '&' in next_url:
        return f'?{next_url}'
    return next_url


def _editable_columns(table_name: str, *, include_pk: bool = False) -> list[dict[str, str]]:
    columns = table_columns(table_name)
    editable = []
    for column in columns:
        if column.name.startswith(HIDDEN_COLUMN_PREFIXES):
            continue
        type_name = str(column.type_code).lower()
        name_lower = column.name.lower()
        display_name = TABLE_FIELD_LABELS.get(table_name, {}).get(column.name, field_display_name(column.name))
        if column.primary_key and not include_pk:
            continue
        editable.append(
            {
                'name': column.name,
                'label': display_name,
                'type': type_name,
                'is_password': column.name in {'password', 'password_hash'} or 'password' in name_lower,
                'is_date': (
                    ('date' in type_name and 'time' not in type_name)
                    or name_lower.endswith('_date')
                    or name_lower in {'birth_date', 'issued_date'}
                ),
                'is_time': 'time' == type_name or name_lower.endswith('_time'),
                'is_datetime': (
                    'timestamp' in type_name
                    or 'datetime' in type_name
                    or name_lower.endswith('_at')
                    or name_lower in {'created_at', 'updated_at', 'joined_at', 'confirmed_at', 'reviewed_at', 'submitted_at', 'expires_at', 'used_at', 'read_at', 'added_at', 'occurred_at', 'resolved_at', 'nickname_changed_at', 'last_login_at'}
                ),
                'is_bool': 'bool' in type_name or name_lower.startswith('is_') or name_lower.startswith('has_') or name_lower.startswith('can_') or name_lower in {'reviewed', 'show_on_map'},
                'is_number': any(token in type_name for token in ('int', 'numeric', 'decimal', 'real', 'double')),
                'is_fk': bool(column.foreign_key_table),
                'related_table': column.foreign_key_table,
                'is_enum': bool(column.type_code and 'enum' in type_name) or name_lower in {
                    'role', 'content_type', 'original_author_type', 'media_type', 'file_type',
                    'collection_type', 'status', 'created_by_role', 'display_mode', 'provider',
                    'target_type', 'type', 'channel', 'chat_kind', 'document_type', 'precision_level',
                    'workplace_type', 'workplace_display_mode', 'notification_type', 'entity_type',
                    'applies_to', 'source', 'action_type',
                },
                'is_media': name_lower in {'file_url', 'image_url', 'avatar_url', 'preview_image_url', 'original_source_url', 'share_url'} or name_lower.endswith('_url'),
                'is_textarea': name_lower in {'bio', 'description', 'details', 'reason', 'reason_text', 'comments', 'rejection_reason', 'decision_note', 'body', 'payload', 'context', 'text', 'public_text_override'},
            }
        )
    return editable


def _prepare_form_payload(
    request: HttpRequest,
    editable_columns: list[dict[str, str]],
    *,
    skip_empty_passwords: bool = False,
) -> dict[str, str]:
    payload: dict[str, str] = {}
    for column in editable_columns:
        value = request.POST.get(column['name'], '')
        file_obj = request.FILES.get(column['name'])
        if column.get('is_media') and not file_obj and not value:
            continue
        if file_obj and column.get('is_media'):
            payload[column['name']] = upload_admin_file(
                file_obj.read(),
                kind='admin',
                owner_id='tables',
                mime_type=getattr(file_obj, 'content_type', None),
                file_name=getattr(file_obj, 'name', None),
            )
        elif column.get('is_media') and value:
            payload[column['name']] = value
        elif column['is_password'] and value:
            payload[column['name']] = make_password(value)
        elif column['is_password'] and skip_empty_passwords and not value:
            continue
        elif column['is_bool']:
            payload[column['name']] = 'true' if value else 'false'
        else:
            payload[column['name']] = value
    return payload


@login_required
def table_create(request: HttpRequest, table_name: str) -> HttpResponse:
    if table_name not in list_tables():
        raise Http404('Table not found')
    editable_columns = _editable_columns(table_name)
    enum_options_map = {column['name']: enum_choices_for_column(table_name, column['name']) for column in editable_columns if column.get('is_enum')}
    related_options_map = {column['name']: related_options(column['related_table']) for column in editable_columns if column['is_fk']}
    next_url = _normalize_next_url(request.POST.get('next') or request.GET.get('next'), table_name)
    if request.method == 'POST':
        if table_name == 'users' and not (request.POST.get('email', '').strip() or request.POST.get('phone', '').strip()):
            messages.error(request, 'Для пользователя нужно указать email или телефон')
        else:
            try:
                save_row(table_name, _prepare_form_payload(request, editable_columns), existing_pk=None)
                messages.success(request, 'Запись создана')
                return HttpResponseRedirect(next_url)
            except ValueError as exc:
                messages.error(request, f'Не удалось создать запись: {exc}')
            except Exception as exc:  # noqa: BLE001
                messages.error(request, f'Не удалось создать запись: {exc}')
    return render(
        request,
        'dashboard/table_form.html',
        {
            'table_name': table_name,
            'editable_columns': editable_columns,
            'enum_options_map': enum_options_map,
            'related_options_map': related_options_map,
            'mode': 'create',
            'next_url': next_url,
        },
    )


@login_required
def table_edit(request: HttpRequest, table_name: str, pk: str) -> HttpResponse:
    if table_name not in list_tables():
        raise Http404('Table not found')
    row = get_row(table_name, pk)
    if row is None:
        raise Http404('Row not found')
    editable_columns = _editable_columns(table_name)
    enum_options_map = {column['name']: enum_choices_for_column(table_name, column['name']) for column in editable_columns if column.get('is_enum')}
    related_options_map = {column['name']: related_options(column['related_table']) for column in editable_columns if column['is_fk']}
    next_url = _normalize_next_url(request.POST.get('next') or request.GET.get('next'), table_name)
    if request.method == 'POST':
        if table_name == 'users' and not (request.POST.get('email', '').strip() or request.POST.get('phone', '').strip()):
            messages.error(request, 'Для пользователя нужно указать email или телефон')
        else:
            try:
                save_row(
                    table_name,
                    _prepare_form_payload(request, editable_columns, skip_empty_passwords=True),
                    existing_pk=pk,
                )
                messages.success(request, 'Запись сохранена')
                return HttpResponseRedirect(next_url)
            except ValueError as exc:
                messages.error(request, f'Не удалось сохранить запись: {exc}')
            except Exception as exc:  # noqa: BLE001
                messages.error(request, f'Не удалось сохранить запись: {exc}')
    return render(
        request,
        'dashboard/table_form.html',
        {
            'table_name': table_name,
            'editable_columns': editable_columns,
            'enum_options_map': enum_options_map,
            'related_options_map': related_options_map,
            'row': row,
            'mode': 'edit',
            'pk': pk,
            'next_url': next_url,
        },
    )


@login_required
def table_delete(request: HttpRequest, table_name: str, pk: str) -> HttpResponse:
    next_url = _normalize_next_url(request.POST.get('next') or request.GET.get('next'), table_name)
    if request.method == 'POST':
        try:
            delete_row(table_name, pk)
            messages.success(request, 'Запись удалена')
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f'Не удалось удалить запись: {exc}')
    return HttpResponseRedirect(next_url)


@login_required
def table_bulk_delete(request: HttpRequest, table_name: str) -> HttpResponse:
    if table_name not in list_tables():
        raise Http404('Table not found')
    next_url = _normalize_next_url(request.POST.get('next') or request.GET.get('next'), table_name)
    if request.method != 'POST':
        return HttpResponseRedirect(next_url)

    selected = [value for value in request.POST.getlist('selected_rows') if value]
    if not selected:
        messages.error(request, 'Укажите хотя бы одну запись для удаления')
        return HttpResponseRedirect(next_url)

    deleted = 0
    errors: list[str] = []
    for pk in selected:
        try:
            delete_row(table_name, pk)
            deleted += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f'{pk}: {exc}')

    if deleted:
        messages.success(request, f'Удалено записей: {deleted}')
    if errors:
        messages.error(request, 'Некоторые записи не удалось удалить: ' + '; '.join(errors[:3]))
    return HttpResponseRedirect(next_url)
