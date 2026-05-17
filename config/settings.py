from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
)
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

# ───────────────────────────────────────────
# Apps
# ───────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'rest_framework.authtoken',  # Token 인증
    'corsheaders',               # CORS
    'drf_spectacular',           # Swagger/OpenAPI

    # Local
    'users',
    'locations',
    'memories',
    'chat',
    'groups',
]

# ───────────────────────────────────────────
# Auth
# ───────────────────────────────────────────
AUTH_USER_MODEL = 'users.User'

# ───────────────────────────────────────────
# Middleware
# ───────────────────────────────────────────
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # 반드시 최상단에 위치
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'config.wsgi.application'

# ───────────────────────────────────────────
# Database (PostgreSQL)
# ───────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST', default='localhost'),
        'PORT': env('DB_PORT', default='5432'),
        'CONN_MAX_AGE': 60,
    }
}

# ───────────────────────────────────────────
# Password Validation
# ───────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ───────────────────────────────────────────
# Internationalization
# ───────────────────────────────────────────
LANGUAGE_CODE = 'ko-kr'
TIME_ZONE = 'Asia/Seoul'
USE_I18N = True
USE_TZ = True

# ───────────────────────────────────────────
# Static / Media
# ───────────────────────────────────────────
STATIC_URL  = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ───────────────────────────────────────────
# Default PK
# ───────────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ───────────────────────────────────────────
# DRF — JWT 인증
# ───────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'users.authentication.BlacklistAwareJWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'user': '10000/hour',
        'chat': '500/hour',
        'login': '5/minute',
        'register': '3/minute',
    },
}

# ───────────────────────────────────────────
# JWT (djangorestframework-simplejwt)
# ───────────────────────────────────────────
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS':  False,
    'AUTH_HEADER_TYPES':      ('Bearer',),
    'USER_ID_FIELD':          'id',
    'USER_ID_CLAIM':          'user_id',
}

# ───────────────────────────────────────────
# Redis — JWT 블랙리스트 (DB 3)
# ───────────────────────────────────────────
REDIS_BLACKLIST_URL = env('REDIS_BLACKLIST_URL', default='redis://localhost:6379/3')

CELERY_BROKER_URL     = env('CELERY_BROKER_URL',     default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='redis://localhost:6379/1')

# ───────────────────────────────────────────
# CORS — 프론트(localhost:5173) 요청 허용
# ───────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:5174',
    'http://127.0.0.1:5174',
]
CORS_ALLOW_CREDENTIALS = True

# ───────────────────────────────────────────
# Email (비밀번호 재설정)
# ───────────────────────────────────────────
EMAIL_BACKEND    = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST       = env('EMAIL_HOST', default='')
EMAIL_PORT       = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS    = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER  = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@mymemorymap.com')
FRONTEND_URL     = env('FRONTEND_URL', default='http://localhost:5173')

# ───────────────────────────────────────────
# Django Cache (Redis DB 2)
# ───────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_CACHE_URL', default='redis://localhost:6379/2'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'TIMEOUT': 300,
    }
}

# ───────────────────────────────────────────
# Gemini API
# ───────────────────────────────────────────
GEMINI_API_KEY = env('GEMINI_API_KEY')
