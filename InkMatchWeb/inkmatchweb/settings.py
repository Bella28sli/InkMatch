from pathlib import Path
import os
from urllib.parse import urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
API_DOTENV = BASE_DIR.parent / 'InkMatchAPI' / '.env'
if API_DOTENV.exists():
    load_dotenv(API_DOTENV)

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'inkmatch-dev-secret-key')
DEBUG = os.getenv('DJANGO_DEBUG', '1') == '1'
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'dashboard.apps.DashboardConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'inkmatchweb.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'inkmatchweb.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'inkmatch',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

database_url = os.getenv('DATABASE_URL', '')
if database_url:
    parsed = urlparse(database_url)
    DATABASES['default'].update(
        {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': (parsed.path or '/inkmatch').lstrip('/'),
            'USER': parsed.username or 'postgres',
            'PASSWORD': parsed.password or 'postgres',
            'HOST': parsed.hostname or 'localhost',
            'PORT': str(parsed.port or '5432'),
        }
    )

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_REDIRECT_URL = '/admin/'
LOGIN_URL = '/admin/login/'
LOGOUT_REDIRECT_URL = '/admin/login/'

ADMIN_SITE_HEADER = 'InkMatch Admin'
ADMIN_SITE_TITLE = 'InkMatch'
ADMIN_INDEX_TITLE = 'Панель управления InkMatch'
