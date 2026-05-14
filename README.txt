InkMatch
========

Инструкция предназначена для проверки проекта InkMatch.

Содержание
----------
1. Если не нужно поднимать локально проект
2. Если нужно поднять локально проект
3. Переменные среды
4. Поля для логинов и паролей

1. Если не нужно поднимать локально проект
------------------------------------------

Если Вы просто хотите посмотреть проект через браузер и приложение, достаточно использовать опубликованные ресурсы.

Основные страницы:
- Главная страница сайта: `https://inkmatch.ru/`
- Страница скачивания APK: `https://inkmatch.ru/static/downloads/InkMatch.apk`
- Django-админка: `https://inkmatch.ru/admin/`
- Внутренняя панель: `https://inkmatch.ru/panel/`
- Список таблиц панели: `https://inkmatch.ru/panel/tables/`
- Swagger UI: `https://inkmatch.ru/docs`
- ReDoc: `https://inkmatch.ru/redoc`

Если проект размещён на другом домене, замените `inkmatch.ru` на адрес этого домена.

APK-файл можно скачать:
- со страницы главной;
- либо напрямую по адресу `https://inkmatch.ru/static/downloads/InkMatch.apk`.

2. Если нужно поднять локально проект
-------------------------------------

Перед запуском убедитесь, что у Вас установлены:
- PostgreSQL;
- Python;
- Flutter;
- Node.js не требуется;
- доступ к локальной папке проекта.

2.0. Как поднять PostgreSQL

Проект использует PostgreSQL и подключается к базе через строку из `DATABASE_URL`.
В текущем `.env` это:

```text
postgresql+psycopg://inkmatch:inkmatch@localhost:5432/inkmatch
```

Значит, локально должны быть выполнены следующие условия:
- PostgreSQL запущен как служба или как отдельный процесс;
- существует база данных `inkmatch`;
- существует пользователь `inkmatch`;
- у пользователя `inkmatch` есть пароль `inkmatch`;
- этому пользователю выданы права на базу `inkmatch`.

Если база и пользователь ещё не созданы, можно сделать это через `psql` или pgAdmin.
Пример для `psql`:

```sql
CREATE USER inkmatch WITH PASSWORD 'inkmatch';
CREATE DATABASE inkmatch OWNER inkmatch;
GRANT ALL PRIVILEGES ON DATABASE inkmatch TO inkmatch;
```

Если Вы используете другой логин, пароль или имя базы, тогда нужно поменять `DATABASE_URL` в `InkMatchAPI/.env`.

2.1. Поднять API

В каталоге `InkMatchAPI` выполните:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Порядок запуска важен:
- сначала создаётся виртуальное окружение;
- затем устанавливаются зависимости;
- затем применяются миграции;
- только после этого запускается сервер.

Если нужно выполнить только миграции, используйте:

```bash
alembic upgrade head
```

Также можно использовать готовый скрипт:

```powershell
.\start_api.ps1
```

Проверка скрипта:
- `start_api.ps1` переходит в папку `InkMatchAPI`;
- активирует `.venv` через `.\.venv\Scripts\activate`;
- выводит адреса запуска;
- запускает `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.

Значит, скрипт работает, если:
- внутри `InkMatchAPI` уже есть `.venv`;
- зависимости уже установлены;
- PostgreSQL и `.env` настроены корректно.

Если `.venv` ещё нет, сначала выполните:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

После этого `start_api.ps1` можно запускать повторно.

2.1.1. Локальные ссылки

При локальном запуске используйте такие адреса:
- Главная страница сайта: `http://127.0.0.1:8000/`
- Страница скачивания APK: `http://127.0.0.1:8000/static/downloads/InkMatch.apk`
- Django-админка: `http://127.0.0.1:8000/admin/`
- Внутренняя панель: `http://127.0.0.1:8000/panel/`
- Список таблиц панели: `http://127.0.0.1:8000/panel/tables/`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

2.2. Поднять Django-сайт и админку

В каталоге `InkMatchWeb` выполните:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

После запуска сайт и админка будут доступны локально на `http://127.0.0.1:8000/`.

2.3. Запустить мобильное приложение

В каталоге `InkMatchMobile` выполните:

```bash
flutter pub get
flutter run
```

Для сборки APK:

```bash
flutter build apk --release
```

Если нужен готовый APK для проверки, положите его в:
- `InkMatchWeb/static/downloads/InkMatch.apk`

3. Переменные среды
-------------------

Ниже перечислены переменные, которые используются в `InkMatchAPI/app/core/config.py` и текущем `InkMatchAPI/.env`.

3.1. База данных и авторизация
- `DATABASE_URL` - строка подключения к PostgreSQL.
- `JWT_SECRET_KEY` - секрет JWT.
- `JWT_ALGORITHM` - алгоритм JWT.
- `ACCESS_TOKEN_TTL_MINUTES` - время жизни access token.
- `REFRESH_TOKEN_TTL_DAYS` - время жизни refresh token.
- `VERIFICATION_CODE_TTL_MINUTES` - время жизни кода подтверждения.

3.2. Push-уведомления
- `PUSH_PROVIDER` - провайдер уведомлений.
- `FCM_SERVER_KEY` - ключ FCM.
- `FIREBASE_PROJECT_ID` - ID Firebase-проекта.
- `FIREBASE_WEB_API_KEY` - web API key Firebase.
- `GOOGLE_APPLICATION_CREDENTIALS` - путь к JSON-файлу service account.

3.3. Email и рассылки
- `UNISENDER_API_KEY` - ключ UniSender.
- `UNISENDER_SENDER_EMAIL` - email отправителя.
- `UNISENDER_SENDER_NAME` - имя отправителя.
- `UNISENDER_API_BASE_URL` - базовый URL UniSender API.
- `SMTP_HOST` - SMTP-хост.
- `SMTP_PORT` - SMTP-порт.
- `SMTP_USERNAME` - SMTP-логин.
- `SMTP_PASSWORD` - SMTP-пароль.
- `SMTP_FROM_EMAIL` - email отправителя.
- `SMTP_FROM_NAME` - имя отправителя.
- `SMTP_USE_TLS` - использовать TLS или нет.

3.4. Медиа и файлы
- `MEDIA_BASE_URL` - базовый URL медиа.
- `YANDEX_STORAGE_ACCESS_KEY_ID` - access key Яндекс Object Storage.
- `YANDEX_STORAGE_SECRET_ACCESS_KEY` - secret key Яндекс Object Storage.
- `YANDEX_STORAGE_BUCKET` - имя бакета.
- `YANDEX_STORAGE_REGION` - регион.
- `YANDEX_STORAGE_ENDPOINT` - endpoint, если он нужен.
- `YANDEX_STORAGE_PUBLIC_BASE_URL` - публичный URL бакета.
- `YANDEX_STORAGE_USE_PRESIGNED_URLS` - использовать presigned URL или нет.
- `YANDEX_STORAGE_PRESIGNED_URL_TTL_SECONDS` - срок действия presigned URL.
- `YANDEX_STORAGE_PREFIX` - префикс в бакете.

3.5. Геокодер и демо-данные
- `YANDEX_GEOCODER_API_KEY` - ключ Яндекс-геокодера.
- `AUTO_SEED_DEMO` - автоматически создавать демо-данные или нет.

3.6. Что обычно менять

Обычно нужно менять:
- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `GOOGLE_APPLICATION_CREDENTIALS`
- `YANDEX_GEOCODER_API_KEY`
- `YANDEX_STORAGE_ACCESS_KEY_ID`
- `YANDEX_STORAGE_SECRET_ACCESS_KEY`
- `YANDEX_STORAGE_BUCKET`
- `YANDEX_STORAGE_PUBLIC_BASE_URL`
- `UNISENDER_API_KEY`
- `UNISENDER_SENDER_EMAIL`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `MEDIA_BASE_URL`, если API доступно не на `127.0.0.1:8000`

Обычно лучше не менять без необходимости:
- `ACCESS_TOKEN_TTL_MINUTES`
- `REFRESH_TOKEN_TTL_DAYS`
- `VERIFICATION_CODE_TTL_MINUTES`
- `JWT_ALGORITHM`
- `PUSH_PROVIDER`
- `YANDEX_STORAGE_REGION`
- `YANDEX_STORAGE_PREFIX`
- `UNISENDER_API_BASE_URL`
- `AUTO_SEED_DEMO`

4. Поля для логинов и паролей
-----------------------------

Ниже заготовки, которые нужно заполнить вручную.

4.1. Django-admin
- Логин: `____________________`
- Пароль: `____________________`

4.2. Администратор
- Логин: `____________________`
- Пароль: `____________________`

4.3. Модератор
- Логин: `____________________`
- Пароль: `____________________`

4.4. Клиент
- Логин: `____________________`
- Пароль: `____________________`

4.5. Мастер
- Логин: `____________________`
- Пароль: `____________________`

5. Короткий порядок проверки
----------------------------

Если локальный запуск не нужен:
- откройте сайт;
- скачайте APK;
- войдите в нужный аккаунт;
- проверьте сценарии в браузере и в приложении.

Если локальный запуск нужен:
- поднимите PostgreSQL;
- запустите API;
- выполните миграции;
- запустите Django-панель;
- запустите Flutter-приложение;
- откройте ссылки из разделов 1 и 2.1.1;
- проверьте входы по заполненным данным из раздела 4.

