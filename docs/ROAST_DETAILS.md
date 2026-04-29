# 🔥 Backend Roast — 상세 설명 및 수정 방법

---

## 🚨 CRITICAL

---

### 1. Gemini API 키 git 히스토리 노출
**파일:** `.env`

**문제:**
`.env`가 `.gitignore`에 있어도, 한 번이라도 `git add .env`를 했다면
`git log --all --full-history -- .env` 로 히스토리에서 꺼낼 수 있음.

**즉시 해야 할 일:**
1. [Google AI Studio](https://aistudio.google.com/apikey) → 해당 키 **Revoke**
2. 새 키 발급 후 `.env`에 업데이트
3. git 히스토리에서 제거 (선택):
```bash
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch .env' \
  --prune-empty --tag-name-filter cat -- --all
```
또는 `git-filter-repo` 사용 (더 안전)

**예방:**
```bash
# .gitignore에 반드시 포함
.env
.env.*
!.env.example
```

---

### 2. `DEBUG=True` 기본값
**파일:** `config/settings.py:7`

**문제:**
```python
env = environ.Env(
    DEBUG=(bool, True),  # ← 기본값이 True
)
```
`.env`에 `DEBUG=False`를 명시하지 않으면 자동으로 `True`가 됨.

**DEBUG=True일 때 구체적으로 무슨 일이 생기냐:**

**① 500 에러 시 전체 내부 정보 노출**

서버에서 에러가 나면 Django가 브라우저에 노란 에러 페이지를 띄움.
이 페이지에는 다음이 전부 포함돼:

```
- 에러가 발생한 소스코드 전체 (파일 경로 포함)
- 해당 시점의 모든 로컬 변수값
- 실행된 SQL 쿼리 전문
- settings.py의 모든 설정값 (SECRET_KEY, DB 비밀번호 포함)
- 설치된 패키지 목록, 파이썬 버전, OS 정보
```

즉, 공격자가 의도적으로 500 에러를 유발하면 DB 접속 정보, 시크릿 키까지 다 볼 수 있음.

**실제로 재현해봄 (2026-04-02)**

`chat/views.py`의 `post()` 첫 줄에 `1/0`을 추가해 ZeroDivisionError를 의도적으로 발생시킴:

```python
def post(self, request):
    1/0  # ZeroDivisionError 강제 발생
    serializer = ChatRequestSerializer(data=request.data)
```

그 다음 curl로 POST 요청을 날렸더니 Django가 92KB짜리 HTML 에러 페이지를 응답으로 반환함:

```bash
curl -X POST http://localhost:8000/api/chat/ \
  -H "Authorization: Token <token>" \
  -d '{"message":"test"}' \
  -o django_error.html
```

**실제로 노출된 정보 (에러 페이지 분석 결과):**

| 정보 | 노출 여부 | 위험도 |
|---|---|---|
| `GEMINI_API_KEY` | Django가 `**`로 마스킹 | 직접 위험은 없음 |
| `DB_PASSWORD` | Django가 `**`로 마스킹 | 직접 위험은 없음 |
| `ANTHROPIC_API_KEY` | Django가 `**`로 마스킹 | 직접 위험은 없음 |
| `DB_HOST: localhost` | **그대로 노출** | DB 위치 파악 가능 |
| `DB_NAME: mymemorymap` | **그대로 노출** | DB 이름 파악 가능 |
| `DB_USER: byunmingyu` | **그대로 노출** | DB 유저명 파악 → 브루트포스 가능 |
| `DB_PORT: 5432` | **그대로 노출** | DB 포트 파악 가능 |
| `HOME: /Users/byunmingyu` | **그대로 노출** | 맥 유저명, 서버 OS 구조 파악 |
| `GEMINI_CLI_IDE_WORKSPACE_PATH` | **그대로 노출** | 프로젝트 전체 경로 노출 |
| `chat/views.py` 소스코드 | **그대로 노출** | API 내부 로직 파악 가능 |
| 스택 트레이스 전체 | **그대로 노출** | 사용 라이브러리, Python 버전 파악 |

**Django 마스킹의 한계:**

Django는 변수명에 `PASSWORD`, `SECRET`, `KEY`, `TOKEN`이 포함된 것만 자동으로 `**`로 가림.
커스텀 변수명을 쓰면 마스킹 안 됨:

```python
GEMINI_API = "AIzaSy..."   # KEY 없으면 그대로 노출
DB_PASS = "1234"            # PASSWORD 없으면 그대로 노출
```

또한 로컬 변수에 담아서 쓰다가 에러가 나면 그 값도 그대로 노출됨:

```python
def my_view(request):
    api_key = settings.GEMINI_API_KEY  # 변수에 담으면
    result = some_api_call(api_key)    # 여기서 에러 나면 api_key 값 그대로 노출
```

**DEBUG=False로 바꾸면:** 위 모든 정보 대신 `{"detail": "Internal Server Error"}` 한 줄만 반환됨.

**② `ALLOWED_HOSTS` 검사 무시**

원래 Django는 요청의 `Host` 헤더가 `ALLOWED_HOSTS` 목록에 없으면 400을 반환함.
DEBUG=True면 이 검사를 건너뜀 → 어떤 도메인에서든 접근 가능.

```
# 예: settings.py에 ALLOWED_HOSTS = ['mymemorymap.com'] 이어도
# DEBUG=True면 http://evil.com 에서 요청해도 통과됨
```

**③ 정적 파일을 Django가 직접 서빙**

운영 환경에서는 정적 파일(JS, CSS, 이미지)을 nginx 같은 웹서버가 서빙해야 빠름.
DEBUG=True면 Django가 직접 서빙 → 요청마다 파이썬 프로세스가 파일을 읽음 → 매우 느림.

**수정:**
```python
env = environ.Env(
    DEBUG=(bool, False),  # 기본값을 False로
)

# settings.py 하단에 추가
if not DEBUG:
    ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')
```

`.env`:
```
DEBUG=True  # 개발 환경에서만 명시적으로 True
```

**✅ 수정 완료 (2026-04-08)**

`config/settings.py:7` 기본값을 `True → False`로 변경:
```python
env = environ.Env(
    DEBUG=(bool, False),  # 기본값 False — .env에 DEBUG=True 명시해야 개발 모드
)
```
이제 `.env`에 `DEBUG=True`가 없으면 자동으로 운영 모드로 동작.

---

### 3. API 레이트 리밋 없음
**파일:** `config/settings.py`, `chat/views.py`

**문제:**
`/api/chat/`은 요청 1건당 Gemini API 1번 호출.
레이트 리밋 없으면 공격자가 초당 수백 번 요청 → Gemini 요금 폭탄.

**수정:**
```python
# settings.py
REST_FRAMEWORK = {
    ...
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '20/hour',
        'user': '200/hour',
    }
}
```

챗 엔드포인트는 더 엄격하게:
```python
# chat/views.py
from rest_framework.throttling import UserRateThrottle

class ChatRateThrottle(UserRateThrottle):
    rate = '30/hour'  # 챗은 시간당 30회

class ChatView(APIView):
    throttle_classes = [ChatRateThrottle]
    ...
```

**✅ 수정 완료 (2026-04-08)**

`config/settings.py` — `REST_FRAMEWORK`에 전역 throttle 추가:
```python
'DEFAULT_THROTTLE_CLASSES': [
    'rest_framework.throttling.AnonRateThrottle',
    'rest_framework.throttling.UserRateThrottle',
],
'DEFAULT_THROTTLE_RATES': {
    'anon': '20/hour',
    'user': '200/hour',
    'chat': '30/hour',
},
```

`chat/views.py` — `ChatView`에 `ChatRateThrottle` 적용:
```python
class ChatRateThrottle(UserRateThrottle):
    scope = 'chat'  # 시간당 30회

class ChatView(APIView):
    throttle_classes = [ChatRateThrottle]
```

초과 시 `429 Too Many Requests` 반환.

---

### 4. 시드 데이터 커맨드 위험
**파일:** `memories/management/commands/seed_data.py`

**문제:**
```bash
python manage.py seed_data --email victim@example.com --clear
# → victim 유저의 모든 Memory 삭제됨
```
서버 접근 권한이 생긴 공격자나 실수로 잘못된 이메일 입력하면 데이터 날아감.

**수정:**
```python
def handle(self, *args, **options):
    if options['clear']:
        # 명시적 확인 요구
        confirm = input(f"'{options['email']}' 유저 데이터를 전부 삭제합니다. 'DELETE' 입력: ")
        if confirm != 'DELETE':
            self.stdout.write('취소됨')
            return
```

---

## ⚠️ MAJOR

---

### 5. 목록 API 페이지네이션 없음
**파일:** `memories/views.py:36-46`
**상태:** ✅ 수정 완료 (백엔드 커밋: 7b0627d / 프런트 커밋: b848813)

**문제:**
```python
def get(self, request):
    memories = Memory.objects.filter(user=request.user)
    # 전부 직렬화해서 반환
    return Response(MemoryListSerializer(memories, many=True).data)
```
기록 10만 개면 응답이 수백 MB. 프런트가 전체를 메모리에 올려야 함.

**수정 내용:**

백엔드 (`memories/views.py`):
```python
class MemoryPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200

class MemoryListCreateView(APIView):
    def get(self, request):
        queryset = Memory.objects.filter(user=request.user)...
        paginator = MemoryPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = MemoryListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
```

응답 포맷이 바뀜:
```json
{
  "count": 500,
  "next": "http://localhost:8000/api/memories/?page=2",
  "previous": null,
  "results": [ ... 50개 ... ]
}
```

프런트 (`useEntries.js`):
- `fetchEntries()`: 1페이지 로드, `entries` 초기화
- `fetchMoreEntries()`: 다음 페이지 로드, `entries`에 append
- `hasMore`: `next` 필드가 있으면 true

프런트 (`Sidebar.jsx`):
- 로컬 slice 제거 → 백엔드가 이미 50개씩 줌
- "더 보기" 버튼 → `onLoadMore()` → `fetchMoreEntries()` → API 호출

**결과:** 로그인 시 50개만 로드, "더 보기" 클릭 시마다 50개씩 추가 API 요청.

---

### 6. 임베딩 실패 시 조용히 넘어감
**파일:** `memories/signals.py:20-22`

**문제:**
```python
def auto_embed_on_save(sender, instance, created, **kwargs):
    try:
        from chat.services import embed_memory
        embed_memory(instance)
    except Exception as e:
        logger.warning(f'자동 임베딩 실패: {e}')
        # 그냥 넘어감. 유저는 모름.
```
기록은 저장됐지만 임베딩이 없으면 RAG 검색에서 영원히 안 나옴.

**수정 방향:**
```python
# Memory 응답에 embedding_status 포함
class MemoryListSerializer(serializers.ModelSerializer):
    embedding_status = serializers.SerializerMethodField()

    def get_embedding_status(self, obj):
        try:
            return 'done' if obj.detail.content_embedding is not None else 'pending'
        except:
            return 'missing'
```

장기적으론 Celery 비동기 태스크로 처리:
```python
# tasks.py
from celery import shared_task

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def embed_memory_task(self, memory_detail_id):
    try:
        md = MemoryDetail.objects.get(pk=memory_detail_id)
        embed_memory(md)
    except Exception as exc:
        raise self.retry(exc=exc)
```

---

### 7. 관련 기록 없어도 Gemini 호출
**파일:** `chat/services.py`

**문제:**
유사한 기록이 0개여도 Gemini에 "관련 기록이 없습니다." 컨텍스트로 API 호출함.
불필요한 토큰 낭비.

**수정:**
```python
# 검색 결과 없으면 Gemini 호출 없이 즉시 반환
if not context_lines:
    ChatSession.objects.create(
        user=user,
        query_text=message,
        ai_response='관련된 기록을 찾지 못했어요. 기록을 더 추가해보세요! 📝',
    )
    return {
        'response': '관련된 기록을 찾지 못했어요. 기록을 더 추가해보세요! 📝',
        'sources': [],
    }
```

---

### 8. lat/lng 유효성 검사 없음
**파일:** `locations/serializers.py`

**문제:**
위도는 -90~90, 경도는 -180~180이어야 하는데 아무 값이나 저장됨.

**수정:**
```python
class LocationCreateSerializer(serializers.Serializer):
    latitude = serializers.FloatField(
        min_value=-90, max_value=90,
        error_messages={'min_value': '위도는 -90 이상이어야 합니다.'}
    )
    longitude = serializers.FloatField(
        min_value=-180, max_value=180,
        error_messages={'max_value': '경도는 180 이하이어야 합니다.'}
    )
```

---

### 9. 검색 파라미터 길이 제한 없음
**파일:** `memories/views.py:39-43`

**문제:**
```python
search = request.query_params.get('search')
if search:
    queryset = queryset.filter(title__icontains=search)
```
`search=AAAAAAA...` (100MB 문자열) 보내면 DB 풀 스캔.

**수정:**
```python
search = request.query_params.get('search', '').strip()[:100]
if len(search) >= 2:  # 최소 2글자 이상만 검색
    from django.db.models import Q
    queryset = queryset.filter(
        Q(title__icontains=search) | Q(tags__name__icontains=search)
    ).distinct()
```

---

### 10. DRF Token 만료 없음
**파일:** `users/views.py`

**문제:**
DRF 기본 Token은 만료 없이 영구 유효.
한 번 탈취되면 사용자가 직접 로그아웃하지 않는 한 영원히 유효.

**수정 옵션 1 - djangorestframework-simplejwt:**
```bash
pip install djangorestframework-simplejwt
```
```python
# settings.py
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}
```

**수정 옵션 2 - Token에 만료 필드 추가 (간단):**
```python
class ExpiringToken(Token):
    class Meta:
        proxy = True

    def is_expired(self):
        return (timezone.now() - self.created).days > 30
```

---

### 11. Memory 생성 트랜잭션 없음
**파일:** `memories/serializers.py:128-152`

**문제:**
```python
def create(self, validated_data):
    memory = Memory.objects.create(...)     # 1. 성공
    MemoryDetail.objects.create(...)        # 2. 성공
    Tag.objects.bulk_create(...)            # 3. 실패 → Memory만 남아서 고아 레코드
```

**수정:**
```python
from django.db import transaction

def create(self, validated_data):
    with transaction.atomic():
        memory = Memory.objects.create(...)
        MemoryDetail.objects.create(...)
        Tag.objects.bulk_create(...)
    return memory
```

---

### 12. 임베딩 차원 3번 변경
**파일:** `memories/migrations/`

**문제:**
- `0002`: 1536차원 (OpenAI 기준)
- `0003`: 768차원 (Gemini text-embedding-004 예상)
- `0004`: 3072차원 (gemini-embedding-001 실제)

1536이나 768 차원으로 저장된 기존 벡터가 있으면 3072 모델과 호환 안 됨.
유사도 검색 결과가 쓰레기가 됨.

**확인 쿼리:**
```sql
SELECT COUNT(*) FROM memory_details WHERE content_embedding IS NOT NULL;
-- 있으면 전부 재임베딩 필요
```

**수정:**
```bash
# 전체 재임베딩
python manage.py embed_memories --all
```

---

## 📝 MINOR

---

### 13. `FloatField` 좌표 정밀도 문제
**파일:** `locations/models.py:68-69`

```python
# 수정 전
latitude = models.FloatField()

# 수정 후 (소수점 6자리 = 약 0.1m 정밀도)
latitude = models.DecimalField(max_digits=9, decimal_places=6)
longitude = models.DecimalField(max_digits=10, decimal_places=6)
```

---

### 14. `Category.__str__` N+1
**파일:** `memories/models.py:43-45`

```python
def __str__(self):
    return f'{self.user.nickname} - {self.name}'
    # admin에서 카테고리 100개 보면 user 쿼리 100번 발생
```

```python
# admin.py에서 list_select_related 추가
class CategoryAdmin(admin.ModelAdmin):
    list_select_related = ('user',)
```

---

### 15. `color_code` hex 검증 없음
**파일:** `memories/models.py:38`

```python
from django.core.validators import RegexValidator

color_code = models.CharField(
    max_length=7,
    default='#007AFF',
    validators=[RegexValidator(r'^#[0-9A-Fa-f]{6}$', '유효한 hex 색상코드를 입력하세요 (예: #FF5733)')]
)
```

---

### 16. `db_index` 없음
**파일:** `memories/models.py`, `chat/models.py`

```python
# 자주 필터링/정렬되는 필드에 인덱스 추가
visited_at = models.DateField(db_index=True)

# ForeignKey는 Django가 자동으로 인덱스 추가하지만 명시해도 좋음
user = models.ForeignKey(..., db_index=True)
```

---

### 17. 테스트 코드 전무

최소한 이것들은 테스트해야 함:
```python
# users/tests.py
class AuthTest(TestCase):
    def test_register(self):
        ...
    def test_login_wrong_password(self):
        ...

# memories/tests.py
class MemoryPermissionTest(TestCase):
    def test_cannot_access_other_users_memory(self):
        ...

# chat/tests.py
class RagChatTest(TestCase):
    def test_chat_without_embeddings(self):
        ...
```

---

### 18. LOGGING 설정 없음
**파일:** `config/settings.py`

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs/django.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'WARNING',
        },
        'chat': {
            'handlers': ['file'],
            'level': 'INFO',
        },
    },
}
```

---

### 19. `numpy` 불필요한 의존성
**파일:** `requirements.txt`

```bash
# 실제로 쓰이는지 확인
grep -r "import numpy" .
# 없으면 제거

pip uninstall numpy
# requirements.txt에서도 삭제
```

---

### 20. 검색 쿼리 비효율
**파일:** `memories/views.py:41-42`

```python
# 수정 전 — 두 번 쿼리 후 union
queryset = queryset.filter(title__icontains=search) | \
           queryset.filter(tags__name__icontains=search)
queryset = queryset.distinct()

# 수정 후 — Q 객체로 한 번에
from django.db.models import Q
queryset = queryset.filter(
    Q(title__icontains=search) | Q(tags__name__icontains=search)
).distinct()
```

---

### 21. `profile_img_url` 검증 없음
**파일:** `users/models.py`

```python
# 수정 전
profile_img_url = models.TextField(null=True, blank=True)

# 수정 후
profile_img_url = models.URLField(null=True, blank=True, max_length=500)
```

---

### 22. 모델명 하드코딩
**파일:** `chat/services.py:28-29`

```python
# 수정 전
CHAT_MODEL = 'gemini-2.5-flash'
EMBEDDING_MODEL = 'gemini-embedding-001'

# 수정 후 — .env에서 읽기
CHAT_MODEL = env('GEMINI_CHAT_MODEL', default='gemini-2.5-flash')
EMBEDDING_MODEL = env('GEMINI_EMBEDDING_MODEL', default='gemini-embedding-001')
```

`.env`:
```
GEMINI_CHAT_MODEL=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
```
