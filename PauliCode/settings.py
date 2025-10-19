"""
Django settings for PauliCode project — Render deployment ready.
"""

from pathlib import Path
import os
from decouple import config
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# =======================
# Security
# =======================
SECRET_KEY = config('DJANGO_SECRET_KEY', default='unsafe-secret-key')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = ['paulicode.onrender.com', 'localhost', '127.0.0.1']

# =======================
# Application definition
# =======================
INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'User',
    'channels',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # must be directly after SecurityMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'PauliCode.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# =======================
# ASGI / WSGI
# =======================
ASGI_APPLICATION = 'PauliCode.asgi.application'
WSGI_APPLICATION = 'PauliCode.wsgi.application'

# =======================
# Database (Render PostgreSQL)
# =======================
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=True
    )
}

# =======================
# Password validation
# =======================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# =======================
# Internationalization
# =======================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'
USE_I18N = True
USE_TZ = True

# =======================
# Static files (Render + WhiteNoise)
# =======================
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'User' / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# =======================
# Media files
# =======================
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# =======================
# Default primary key field
# =======================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =======================
# Jazzmin UI Settings
# =======================
JAZZMIN_SETTINGS = {
    "site_title": "PauliCode Admin",
    "site_header": "PauliCode",
    "site_brand": "PauliCode",
    "welcome_sign": "Welcome to PauliCode Admin",
    "show_ui_builder": True,
}

JAZZMIN_UI_TWEAKS = {
    "theme": "cyborg",
    "dark_mode_theme": "solar",
    "sidebar_fixed": True,
}

# =======================
# Extra for Render (optional fallback)
# =======================
# Allow Django to serve media during Render (since free plan can't use Nginx)
if not DEBUG:
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
