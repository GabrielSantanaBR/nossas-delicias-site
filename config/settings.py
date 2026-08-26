import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get('DEBUG', '0') == '1'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-only-change-me')

if not DEBUG and SECRET_KEY == 'dev-only-change-me':
    raise ImproperlyConfigured('DJANGO_SECRET_KEY precisa ser configurado em produção.')


def csv_env(name, default=''):
    return [value.strip() for value in os.environ.get(name, default).split(',') if value.strip()]


railway_host = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '').strip()
render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME', '').strip()
public_domain = os.environ.get('PUBLIC_DOMAIN', '').strip()
dynamic_hosts = [host for host in (railway_host, render_host, public_domain) if host]
ALLOWED_HOSTS = list(dict.fromkeys(csv_env('ALLOWED_HOSTS', 'localhost,127.0.0.1') + dynamic_hosts))

trusted_defaults = [f'https://{host}' for host in dynamic_hosts]
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(csv_env('CSRF_TRUSTED_ORIGINS') + trusted_defaults))
PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', '').rstrip('/')
if not PUBLIC_BASE_URL and public_domain:
    PUBLIC_BASE_URL = f'https://{public_domain}'
elif not PUBLIC_BASE_URL and railway_host:
    PUBLIC_BASE_URL = f'https://{railway_host}'

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',
    'channels',
    'storages',
    'store.apps.StoreConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'store.middleware.SecurityHeadersMiddleware',
]

ROOT_URLCONF = 'config.urls'
TEMPLATES = [{
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
}]
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
if not DEBUG and not DATABASE_URL:
    raise ImproperlyConfigured('DATABASE_URL precisa apontar para PostgreSQL em produção.')
DATABASES = {
    'default': dj_database_url.config(
        default=DATABASE_URL or f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=60,
        conn_health_checks=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]
PASSWORD_RESET_TIMEOUT = 3600

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

static_backend = (
    'django.contrib.staticfiles.storage.StaticFilesStorage'
    if DEBUG
    else 'whitenoise.storage.CompressedManifestStaticFilesStorage'
)
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': static_backend},
}
R2_ACCOUNT_ID = os.environ.get('R2_ACCOUNT_ID')
R2_BUCKET_NAME = os.environ.get('R2_BUCKET_NAME')
if R2_ACCOUNT_ID and R2_BUCKET_NAME and os.environ.get('R2_ACCESS_KEY_ID') and os.environ.get('R2_SECRET_ACCESS_KEY'):
    STORAGES['default'] = {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': {
            'bucket_name': R2_BUCKET_NAME,
            'access_key': os.environ['R2_ACCESS_KEY_ID'],
            'secret_key': os.environ['R2_SECRET_ACCESS_KEY'],
            'endpoint_url': f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
            'region_name': 'auto',
            'custom_domain': os.environ.get('R2_PUBLIC_DOMAIN') or None,
            'default_acl': None,
            'querystring_auth': False,
        },
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'account'
LOGOUT_REDIRECT_URL = 'home'

SESSION_COOKIE_NAME = 'nd_sessionid'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = True

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if not DEBUG:
    SECURE_SSL_REDIRECT = os.environ.get('DISABLE_HTTPS_REDIRECT', '0') != '1'
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get('HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get('HSTS_INCLUDE_SUBDOMAINS', '1') == '1'
    SECURE_HSTS_PRELOAD = os.environ.get('HSTS_PRELOAD', '0') == '1'

DATA_UPLOAD_MAX_MEMORY_SIZE = 8 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000
FILE_UPLOAD_PERMISSIONS = 0o640

OTP_ADMIN_HIDE_SENSITIVE_DATA = True
OTP_TOTP_ISSUER = 'Nossas Delicias Admin'
OTP_TOTP_THROTTLE_FACTOR = 1

REDIS_URL = os.environ.get('REDIS_URL', '').strip()
if REDIS_URL:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [REDIS_URL], 'capacity': 500, 'expiry': 60},
        }
    }
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
            'TIMEOUT': 300,
        }
    }
elif DEBUG or os.environ.get('ALLOW_INMEMORY_CHANNEL_LAYER') == '1':
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'nossas-delicias-dev'}}
else:
    raise ImproperlyConfigured('REDIS_URL é obrigatório em produção para chat e rate limiting consistentes.')

MERCADO_PAGO_ACCESS_TOKEN = os.environ.get('MERCADO_PAGO_ACCESS_TOKEN', '')
MERCADO_PAGO_WEBHOOK_SECRET = os.environ.get('MERCADO_PAGO_WEBHOOK_SECRET', '')

EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', '1') == '1'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'Nossas Delícias <no-reply@nossasdelicias.com.br>')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': os.environ.get('LOG_LEVEL', 'INFO')},
    'loggers': {
        'django.security': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'store': {'handlers': ['console'], 'level': os.environ.get('LOG_LEVEL', 'INFO'), 'propagate': False},
    },
}
