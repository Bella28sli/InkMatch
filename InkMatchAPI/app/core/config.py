from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    app_name: str = 'InkMatchAPI'
    api_v1_prefix: str = '/api/v1'
    database_url: str = Field(
        default='postgresql+psycopg://postgres:postgres@localhost:5432/inkmatch',
        validation_alias='DATABASE_URL',
    )
    jwt_secret_key: str = 'CHANGE_ME'
    jwt_algorithm: str = 'HS256'
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 60
    verification_code_ttl_minutes: int = 10

    push_provider: str = Field(default='log', validation_alias='PUSH_PROVIDER')
    fcm_server_key: str | None = Field(default=None, validation_alias='FCM_SERVER_KEY')
    firebase_project_id: str | None = Field(default=None, validation_alias='FIREBASE_PROJECT_ID')
    firebase_web_api_key: str | None = Field(default=None, validation_alias='FIREBASE_WEB_API_KEY')
    google_application_credentials: str | None = Field(default=None, validation_alias='GOOGLE_APPLICATION_CREDENTIALS')
    smtp_host: str | None = Field(default=None, validation_alias='SMTP_HOST')
    smtp_port: int = Field(default=587, validation_alias='SMTP_PORT')
    smtp_username: str | None = Field(default=None, validation_alias='SMTP_USERNAME')
    smtp_password: str | None = Field(default=None, validation_alias='SMTP_PASSWORD')
    smtp_from_email: str | None = Field(default=None, validation_alias='SMTP_FROM_EMAIL')
    smtp_from_name: str = Field(default='InkMatch', validation_alias='SMTP_FROM_NAME')
    smtp_use_tls: bool = Field(default=True, validation_alias='SMTP_USE_TLS')
    media_base_url: str = Field(default='http://127.0.0.1:8000', validation_alias='MEDIA_BASE_URL')
    yandex_geocoder_api_key: str | None = Field(default=None, validation_alias='YANDEX_GEOCODER_API_KEY')
    yandex_storage_access_key_id: str | None = Field(default=None, validation_alias='YANDEX_STORAGE_ACCESS_KEY_ID')
    yandex_storage_secret_access_key: str | None = Field(default=None, validation_alias='YANDEX_STORAGE_SECRET_ACCESS_KEY')
    yandex_storage_bucket: str | None = Field(default=None, validation_alias='YANDEX_STORAGE_BUCKET')
    yandex_storage_region: str = Field(default='ru-central1', validation_alias='YANDEX_STORAGE_REGION')
    yandex_storage_endpoint: str | None = Field(default=None, validation_alias='YANDEX_STORAGE_ENDPOINT')
    yandex_storage_public_base_url: str | None = Field(default=None, validation_alias='YANDEX_STORAGE_PUBLIC_BASE_URL')
    yandex_storage_use_presigned_urls: bool = Field(default=False, validation_alias='YANDEX_STORAGE_USE_PRESIGNED_URLS')
    yandex_storage_presigned_url_ttl_seconds: int = Field(default=3600, validation_alias='YANDEX_STORAGE_PRESIGNED_URL_TTL_SECONDS')
    yandex_storage_prefix: str = Field(default='inkmatch', validation_alias='YANDEX_STORAGE_PREFIX')

    auto_seed_demo: bool = Field(default=True, validation_alias='AUTO_SEED_DEMO')


settings = Settings()
