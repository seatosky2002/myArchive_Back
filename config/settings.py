from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),  # 기본값 False — .env에 DEBUG=True 명시해야 개발 모드
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
    'rest_framework.authtoken',              # Token 인증 (레거시, 추후 제거)
    # 'rest_framework_simplejwt.token_blacklist' 제거 — Redis 블랙리스트로 대체
    'corsheaders',                           # CORS
    'drf_spectacular',                       # Swagger/OpenAPI

    # Local
    'users',
    'locations',
    'memories',
    'chat',
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
# Static
# ───────────────────────────────────────────
STATIC_URL = 'static/'

# ───────────────────────────────────────────
# Default PK
# ───────────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ───────────────────────────────────────────
# DRF — Token 인증으로 전환 (SPA 친화적)
# ───────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'users.authentication.BlacklistAwareJWTAuthentication',  # 블랙리스트 검사 포함
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '20/hour',
        'user': '200/hour',
        'chat': '30/hour',
    },
}

# ───────────────────────────────────────────
# JWT (djangorestframework-simplejwt)
# ───────────────────────────────────────────
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS':  False,  # 회전은 CookieTokenRefreshView에서 직접 처리
    'AUTH_HEADER_TYPES':      ('Bearer',),
    'USER_ID_FIELD':          'id',
    'USER_ID_CLAIM':          'user_id',
}

# Redis DB 3 — JWT 블랙리스트
REDIS_BLACKLIST_URL = env('REDIS_BLACKLIST_URL', default='redis://localhost:6379/3')

# ───────────────────────────────────────────
# drf-spectacular (Swagger/OpenAPI)
# ───────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    'TITLE': 'MyMemoryMap API',
    'DESCRIPTION': '위치 기반 개인 기록 서비스 MyMemoryMap의 REST API',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# ───────────────────────────────────────────
# CORS — 프론트(localhost:5173) 요청 허용
# ───────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
]
CORS_ALLOW_CREDENTIALS = True

# ───────────────────────────────────────────
# Gemini API
# ───────────────────────────────────────────
GEMINI_API_KEY = env('GEMINI_API_KEY')

# ───────────────────────────────────────────
# Celery — Redis DB 0 (태스크 큐)
# ───────────────────────────────────────────
CELERY_BROKER_URL     = env('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('REDIS_URL', default='redis://localhost:6379/0')
CELERY_TASK_SERIALIZER   = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT    = ['json']
CELERY_TIMEZONE          = 'Asia/Seoul'

# ───────────────────────────────────────────
# Cache — Redis DB 2 (레이트 리밋 카운터)
# DRF Throttle이 Django cache framework를 사용하므로
# Redis로 전환하면 재시작 시 카운터 초기화 문제 해결
# ───────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_CACHE_URL', default='redis://localhost:6379/2'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'mymemorymap',
    }
}
