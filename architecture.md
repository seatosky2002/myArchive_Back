# MyMemoryMap — 프로덕션 아키텍처 설계서

---

## 1. 전체 아키텍처 다이어그램

### 현재 (AS-IS)

```
┌─────────────────────────────────────────────────────────────┐
│                        클라이언트                            │
│              React SPA (Vite, Kakao Maps SDK)               │
└──────────────────────────┬──────────────────────────────────┘
                           │  HTTPS / REST API
                           │  Authorization: Token <key>
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Django + DRF (단일 프로세스)                │
│                                                             │
│  /api/users/      → users/views.py    → Token 인증          │
│  /api/locations/  → locations/views.py                      │
│  /api/memories/   → memories/views.py                       │
│  /api/chat/       → chat/views.py                           │
│                         │                                   │
│             기록 저장 시  │  signals.py → embed_memory()     │
│                         │  ← Gemini API 동기 호출 (블로킹!)  │
└──────────┬──────────────┴───────────────────────────────────┘
           │                           │
           ▼                           ▼
┌──────────────────┐         ┌──────────────────────┐
│   PostgreSQL     │         │     Gemini API        │
│  + pgvector      │         │  (임베딩 + 채팅)       │
│                  │         │  외부 네트워크 의존     │
│  memories        │         └──────────────────────┘
│  memory_details  │
│  locations       │
│  chat_sessions   │
└──────────────────┘
```

**현재 문제점 요약:**
- Django 프로세스 하나가 API 서빙 + 임베딩 Gemini 호출을 모두 동기 처리
- 기록 저장 시 Gemini 응답 올 때까지 HTTP 응답이 블로킹됨 (최대 3~5초)
- 레이트 리밋 카운터가 로컬 메모리 → 재시작 시 초기화
- Token 영구 유효 → 탈취 시 무기한 사용 가능

---

### 목표 (TO-BE)

```
┌─────────────────────────────────────────────────────────────────────┐
│                           클라이언트                                  │
│                    React SPA (Vite, Kakao Maps SDK)                  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  HTTPS
                               │  Authorization: Bearer <access_token>
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Django + DRF                                  │
│                                                                      │
│  /api/users/      → JWT 발급 (access 1h / refresh 7d)               │
│  /api/locations/  → 장소 저장                                        │
│  /api/memories/   → 기록 CRUD  ──────────────────────┐              │
│  /api/chat/       → RAG 채팅                          │              │
│  /api/schema/     → OpenAPI 스키마                    │ 기록 저장 후  │
│  /api/docs/       → Swagger UI                       │ 태스크 발행   │
└───────────┬───────────────────────────────────────────┼─────────────┘
            │                                           │
            │  DB 읽기/쓰기                              │  publish
            ▼                                           ▼
┌───────────────────┐                      ┌───────────────────────────┐
│   PostgreSQL      │                      │       Redis               │
│   + pgvector      │                      │                           │
│                   │◄─────────────────────│  ① Celery 태스크 큐       │
│  memories         │   임베딩 저장          │  ② 레이트 리밋 카운터      │
│  memory_details   │                      │  ③ JWT 블랙리스트          │
│  locations        │                      │  ④ 캐시 (카테고리 목록 등) │
│  chat_sessions    │                      └──────────┬────────────────┘
└───────────────────┘                                 │  consume
                                                      ▼
                                         ┌────────────────────────────┐
                                         │      Celery Worker         │
                                         │                            │
                                         │  embed_memory_task()       │
                                         │    → Gemini Embedding API  │
                                         │    → memory_details 업데이트│
                                         │                            │
                                         │  max_retries=3             │
                                         │  retry_delay=60s           │
                                         └────────────────────────────┘
                                                      │
                                                      ▼
                                         ┌────────────────────────────┐
                                         │       Gemini API           │
                                         │  gemini-embedding-001      │
                                         │  gemini-2.5-flash          │
                                         └────────────────────────────┘
```

---

## 2. 인증 개선 — DRF Token → JWT

### 현재 구조와 문제

```python
# 현재: users/views.py
token, _ = Token.objects.get_or_create(user=user)
# → DB에 영구 저장, 만료 없음, 탈취 시 무기한 유효
```

```
현재 Token 흐름:
로그인 → DB에서 Token 조회/생성 → 응답
매 요청 → DB에서 Token 조회 (매번 DB hit!)
```

### JWT 전환 후

```
JWT 흐름:
로그인 → access_token(1h) + refresh_token(7d) 발급 (DB hit 없음)
매 요청 → access_token 서명 검증만 (DB hit 없음!)
access 만료 → /api/users/token/refresh/ 에 refresh_token 전송 → 새 access 발급
로그아웃 → refresh_token을 Redis 블랙리스트에 추가
```

### 설치 및 설정

```bash
pip install djangorestframework-simplejwt
```

```python
# config/settings.py

from datetime import timedelta

INSTALLED_APPS += ['rest_framework_simplejwt.token_blacklist']

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    ...
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS':  True,   # refresh 사용 시 새 refresh 발급
    'BLACKLIST_AFTER_ROTATION': True, # 이전 refresh는 블랙리스트 처리
    'AUTH_HEADER_TYPES': ('Bearer',),
}
```

```python
# users/views.py — 로그인 응답 변경
from rest_framework_simplejwt.tokens import RefreshToken

class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        refresh = RefreshToken.for_user(user)
        return Response({
            'access':  str(refresh.access_token),
            'refresh': str(refresh),
            'user':    UserSerializer(user).data,
        })

class LogoutView(APIView):
    def post(self, request):
        refresh_token = request.data.get('refresh')
        token = RefreshToken(refresh_token)
        token.blacklist()  # Redis 블랙리스트에 추가
        return Response({'detail': '로그아웃 되었습니다.'})
```

```python
# config/urls.py — 토큰 갱신 엔드포인트 추가
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns += [
    path('api/users/token/refresh/', TokenRefreshView.as_view()),
]
```

### 프론트 변경 (useAuth.js)

```
현재: sessionStorage에 token 1개 저장
변경: sessionStorage에 access_token + refresh_token 저장
     access 401 시 → /api/users/token/refresh/ 자동 재발급
     refresh도 만료 시 → 로그인 페이지로 이동
```

### DRF Token vs JWT 트레이드오프

| | DRF Token | JWT |
|---|---|---|
| DB hit (매 요청) | O (토큰 조회) | X (서명 검증만) |
| 즉시 무효화 | O (DB 삭제) | 어려움 (블랙리스트 필요) |
| 만료 | 없음 (직접 구현 필요) | 기본 제공 |
| 탈취 대응 | 토큰 삭제로 즉시 차단 | access 만료까지 대기 |
| 구현 복잡도 | 낮음 | 중간 |

---

## 3. 비동기 처리 — Celery + Redis

### 현재 동기 흐름 (문제)

```
클라이언트         Django              Gemini API
    │                │                      │
    │  POST /memories/│                      │
    │────────────────►│                      │
    │                 │  embed_content()     │
    │                 │─────────────────────►│
    │                 │                      │  (1~3초 대기)
    │                 │◄─────────────────────│
    │  201 Created    │  DB 저장             │
    │◄────────────────│                      │
```

기록 저장 API가 Gemini API 응답까지 기다려야 해서 느림.
네트워크 문제 시 기록 저장 자체가 실패할 수 있음.

### 목표 비동기 흐름

```
클라이언트         Django            Redis 큐        Celery Worker     Gemini API
    │                │                  │                  │                │
    │  POST /memories/│                  │                  │                │
    │────────────────►│                  │                  │                │
    │                 │  DB 저장         │                  │                │
    │                 │  (Memory+Detail) │                  │                │
    │  201 Created    │                  │                  │                │
    │◄────────────────│  태스크 발행      │                  │                │
    │                 │─────────────────►│                  │                │
    │                 │                  │  태스크 소비       │                │
    │                 │                  │─────────────────►│                │
    │                 │                  │                  │  embed_content()│
    │                 │                  │                  │───────────────►│
    │                 │                  │                  │◄───────────────│
    │                 │                  │                  │  DB 업데이트    │
    │                 │                  │                  │  (content_embedding)
```

API 응답이 즉각적. 임베딩은 백그라운드에서 처리.

### 설치

```bash
pip install celery redis django-celery-results
```

### 설정

```python
# config/settings.py

INSTALLED_APPS += ['django_celery_results']

CELERY_BROKER_URL        = env('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND    = 'django-db'  # 태스크 결과를 DB에 저장
CELERY_TASK_SERIALIZER   = 'json'
CELERY_ACCEPT_CONTENT    = ['json']
CELERY_TIMEZONE          = 'Asia/Seoul'
```

```python
# config/celery.py  ← 새 파일

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('mymemorymap')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

```python
# config/__init__.py 수정

from .celery import app as celery_app
__all__ = ('celery_app',)
```

```python
# chat/tasks.py  ← 새 파일

from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 실패 시 60초 후 재시도
    name='chat.tasks.embed_memory_task',
)
def embed_memory_task(self, memory_detail_id):
    from memories.models import MemoryDetail
    from chat.services import embed_memory

    try:
        md = MemoryDetail.objects.select_related('memory').get(pk=memory_detail_id)
        embed_memory(md)
        logger.info(f'임베딩 완료: memory_id={memory_detail_id}')
    except Exception as exc:
        logger.error(f'임베딩 실패 (시도 {self.request.retries + 1}/3): {exc}')
        raise self.retry(exc=exc)
```

```python
# memories/signals.py  ← 수정

def auto_embed_on_save(sender, instance, created, **kwargs):
    if not created:
        return

    # 동기 호출 제거 → 큐에 태스크 발행
    from chat.tasks import embed_memory_task
    embed_memory_task.delay(str(instance.memory_id))
    # .delay()는 즉시 반환 — Django는 블로킹 없이 201 응답
```

### Celery Worker 실행

```bash
# 개발 환경
celery -A config worker --loglevel=info

# 프로덕션 (동시 4개 처리)
celery -A config worker --concurrency=4 --loglevel=warning
```

---

## 4. 캐싱 전략 — Redis

### 캐싱할 대상 선정

```
캐싱 O:
  ✓ 카테고리 목록 (GET /api/memories/categories/)
    → 자주 읽히고 자주 안 바뀜. 유저별로 캐시.
  ✓ 유저 프로필 (GET /api/users/me/)
    → 매 요청마다 DB 조회 중. 짧은 TTL로 캐시.
  ✓ 특정 Location 정보 (kakao_place_id로 조회)
    → 한번 저장된 장소는 변하지 않음.

캐싱 X:
  ✗ 기록 목록 (자주 바뀜, 유저별 필터/정렬)
  ✗ RAG 채팅 결과 (질문마다 다름)
```

### Redis 캐시 설정

```bash
pip install django-redis
```

```python
# config/settings.py

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'mymemorymap',
    }
}
```

### 캐시 적용 예시

```python
# memories/views.py — 카테고리 목록 캐시
from django.core.cache import cache

class CategoryListCreateView(APIView):
    def get(self, request):
        cache_key = f'categories:{request.user.id}'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        categories = Category.objects.filter(user=request.user)
        data = CategorySerializer(categories, many=True).data
        cache.set(cache_key, data, timeout=60 * 10)  # 10분
        return Response(data)

    def post(self, request):
        # ... 생성 후 캐시 무효화
        cache.delete(f'categories:{request.user.id}')
```

### Redis 키 설계

```
mymemorymap:categories:{user_id}         TTL: 10분
mymemorymap:user_profile:{user_id}       TTL: 5분
mymemorymap:location:{kakao_place_id}    TTL: 24시간
mymemorymap:throttle:chat:{user_id}      TTL: 1시간 (레이트 리밋 카운터)
mymemorymap:jwt_blacklist:{jti}          TTL: refresh_token 만료시간
```

---

## 5. 레이트 리밋 보강 — Redis 백엔드

### 현재 문제

```python
# 현재: 로컬 메모리 캐시 사용
# → Django 재시작 시 카운터 초기화
# → 멀티 프로세스 환경에서 카운터 공유 안 됨
```

### Redis로 전환

```python
# config/settings.py

# CACHES를 Redis로 바꾸면 DRF Throttle도 자동으로 Redis 사용
# (DRF는 Django cache framework 사용하기 때문)

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://localhost:6379/1'),
        ...
    }
}

# 이것만으로 ThrottleRate 카운터가 Redis에 저장됨
# 재시작해도 카운터 유지, 멀티 프로세스 공유 가능
```

---

## 6. 에러 핸들링 & 모니터링

### Sentry 연동

```bash
pip install sentry-sdk
```

```python
# config/settings.py

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

sentry_sdk.init(
    dsn=env('SENTRY_DSN', default=''),
    integrations=[
        DjangoIntegration(),
        CeleryIntegration(),  # Celery 태스크 에러도 수집
    ],
    traces_sample_rate=0.1,   # 요청의 10%만 성능 트레이싱 (비용 절감)
    send_default_pii=False,   # 개인정보 전송 금지
    environment=env('DJANGO_ENV', default='production'),
)
```

### LOGGING 설정

```python
# config/settings.py

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs/django.log',
            'maxBytes': 10 * 1024 * 1024,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
        },
        'memories': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
        'chat': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
    },
}
```

---

## 7. 테스트 전략

### 우선순위

```
P0 (지금 당장):
  1. 타 유저 기록 접근 차단 (보안 핵심)
  2. 기록 CRUD 기본 동작

P1 (다음 스프린트):
  3. 인증 흐름 (로그인/로그아웃/토큰 갱신)
  4. Celery 임베딩 태스크 (모킹)

P2 (나중에):
  5. RAG 채팅 (Gemini 모킹)
  6. 레이트 리밋
```

### 핵심 테스트 코드

```python
# memories/tests.py

from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()

class MemoryPermissionTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user(email='a@test.com', password='pw', nickname='a')
        self.user_b = User.objects.create_user(email='b@test.com', password='pw', nickname='b')

    def test_cannot_read_other_users_memory(self):
        """user_b가 user_a의 기록에 접근 → 404"""
        self.client.force_authenticate(user=self.user_b)
        res = self.client.get(f'/api/memories/{self.memory_a.id}/')
        self.assertEqual(res.status_code, 404)

    def test_cannot_delete_other_users_memory(self):
        """user_b가 user_a의 기록 삭제 시도 → 404"""
        self.client.force_authenticate(user=self.user_b)
        res = self.client.delete(f'/api/memories/{self.memory_a.id}/')
        self.assertEqual(res.status_code, 404)


# chat/tests.py

from unittest.mock import patch

class EmbedTaskTest(TestCase):
    @patch('chat.services.embed_memory')  # Gemini 실제 호출 차단
    def test_embed_task_retries_on_failure(self, mock_embed):
        mock_embed.side_effect = Exception('Gemini 오류')
        with self.assertRaises(Exception):
            embed_memory_task(str(self.memory_detail.pk))
        self.assertEqual(mock_embed.call_count, 3)
```

---

## 8. 배포 구조 — Docker Compose

### 컨테이너 구성

```yaml
# docker-compose.yml

version: '3.9'

services:

  # ── PostgreSQL ────────────────────────────────
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB:       mymemorymap
      POSTGRES_USER:     ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      retries: 5

  # ── Redis ─────────────────────────────────────
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s

  # ── Django API 서버 ───────────────────────────
  api:
    build: .
    command: gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      db:    { condition: service_healthy }
      redis: { condition: service_healthy }
    volumes:
      - ./logs:/app/logs

  # ── Celery Worker ──────────────────────────────
  worker:
    build: .
    command: celery -A config worker --concurrency=2 --loglevel=warning
    env_file: .env
    depends_on:
      db:    { condition: service_healthy }
      redis: { condition: service_healthy }
    volumes:
      - ./logs:/app/logs

volumes:
  postgres_data:
  redis_data:
```

### 컨테이너 역할 요약

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│   api         │   │   worker      │   │   redis       │   │   db          │
│  (Django +   │   │  (Celery)     │   │               │   │  (Postgres   │
│   gunicorn)  │   │               │   │  ① 태스크 큐  │   │   + pgvector)│
│              │──►│               │   │  ② 캐시       │   │              │
│  4 workers   │   │  임베딩 처리   │   │  ③ 세션/리밋  │   │  데이터 영구  │
│  포트 8000   │   │  Gemini 호출  │   │               │   │  저장         │
└──────┬───────┘   └──────┬────────┘   └──────┬────────┘   └──────┬───────┘
       │                  │                   ▲                    ▲
       └──────────────────┴───────────────────┘                    │
                          태스크 발행/소비                           │
       └─────────────────────────────────────────────────────────-─┘
                              DB 읽기/쓰기
```

---

## 구현 우선순위

| 우선순위 | 항목 | 난이도 | 효과 |
|---|---|---|---|
| **P0** | Celery + Redis 비동기 임베딩 | 중 | API 응답 즉각화, 안정성 |
| **P0** | Redis 캐시 백엔드 전환 | 하 | 레이트 리밋 신뢰성 |
| **P1** | JWT 전환 | 중 | 보안, DB hit 감소 |
| **P1** | Sentry 연동 | 하 | 에러 모니터링 |
| **P1** | LOGGING 설정 | 하 | 운영 가시성 |
| **P2** | Docker Compose | 중 | 배포 표준화 |
| **P2** | 테스트 코드 | 중 | 회귀 방지 |
