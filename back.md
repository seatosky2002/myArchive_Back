# MyMemoryMap — 백엔드 구조 문서

## 기술 스택

| 항목 | 내용 |
|------|------|
| Framework | Django 5.2 + Django REST Framework 3.17 |
| Database | PostgreSQL + pgvector |
| Auth | JWT (`djangorestframework-simplejwt`) — access token(1h) + httpOnly 쿠키 refresh token(7d) |
| Cache / Queue | Redis (DB 0: Celery 브로커, DB 2: 레이트리밋, DB 3: JWT 블랙리스트) |
| Async | Celery (Gemini 임베딩 비동기 처리) |
| Python | 3.10 |

---

## 프로젝트 구조

```
Back_myArchive/
├── config/
│   ├── settings.py       # 환경변수, 앱 등록, DB, DRF, JWT, Redis, Celery 설정
│   ├── urls.py           # 루트 URL + media 파일 서빙 (개발)
│   └── celery.py         # Celery 앱 초기화
├── users/                # 인증 (JWT), 프로필
│   ├── authentication.py # BlacklistAwareJWTAuthentication
│   └── blacklist.py      # Redis DB 3 기반 JWT 블랙리스트
├── locations/            # 주소 정규화 및 장소 관리
├── memories/             # 기록 CRUD, 태그, 카테고리, 이미지 업로드
├── chat/                 # RAG 챗봇, Gemini 임베딩 태스크
├── media/                # 업로드 파일 저장 (memory_images/년/월/)
└── requirements.txt
```

---

## 앱별 역할

### 📂 users

**역할:** 회원가입, 로그인, 로그아웃, 토큰 갱신, 내 프로필 조회/수정

**모델:** `User` (AbstractUser 상속, UUID PK, email 로그인)

**엔드포인트:**

| Method | URL | 설명 |
|--------|-----|------|
| POST | `/api/users/register/` | 회원가입 → `{access, user}` + refresh 쿠키 |
| POST | `/api/users/login/` | 로그인 → `{access, user}` + refresh 쿠키 |
| POST | `/api/users/logout/` | 로그아웃 (access + refresh 블랙리스트 등록) |
| POST | `/api/users/token/refresh/` | access 토큰 갱신 (쿠키의 refresh 사용) |
| GET/PUT | `/api/users/me/` | 내 프로필 조회/수정 |

**인증 흐름:**
- 로그인 → `access` 토큰은 응답 body, `refresh` 토큰은 httpOnly 쿠키로 분리 발급
- 프론트는 `Authorization: Bearer <access>` 헤더로 요청
- access 만료 시 401 → 프론트가 `/token/refresh/` 자동 호출 (쿠키 자동 전송)
- 로그아웃 시 두 토큰의 JTI를 Redis DB 3에 TTL과 함께 저장 (블랙리스트)
- `BlacklistAwareJWTAuthentication`: 모든 요청에서 JTI를 Redis에 조회하여 블랙리스트 여부 확인

---

### 📂 locations

**역할:** 카카오 API에서 받은 장소 정보를 3단계 주소로 정규화하여 저장. 동일 장소는 중복 저장하지 않음.

**모델:**
- `AddressRegion`: 행정구역 (시/도, 구/군, 동)
- `AddressDetail`: 도로명/지번 상세 주소
- `Location`: 최종 POI (kakao_place_id 기준 dedup)

**엔드포인트:**

| Method | URL | 설명 |
|--------|-----|------|
| POST | `/api/locations/` | 장소 생성 또는 기존 장소 반환 |
| GET | `/api/locations/<id>/` | 장소 상세 조회 |

---

### 📂 memories

**역할:** 기록 CRUD. 목록(경량)과 상세(중량) 분리 조회. 카테고리, 태그, 이미지 관리.

**모델:**
- `Memory`: 경량 메타 (제목, 무드, 날씨, 날짜, 위치)
- `MemoryDetail`: 중량 본문 + AI 벡터 (1:1 수직 파티셔닝)
- `Category`: 사용자별 카테고리
- `Tag`: 기록별 태그 (unique per memory)
- `MemoryImage`: 첨부 이미지 (`ImageField`, null 허용)
- `ChatSession`: AI 채팅 기록

**엔드포인트:**

| Method | URL | 설명 |
|--------|-----|------|
| GET | `/api/memories/` | 기록 목록 (경량) |
| POST | `/api/memories/` | 기록 생성 |
| GET | `/api/memories/<id>/` | 기록 상세 (본문 + 이미지 포함) |
| PUT | `/api/memories/<id>/` | 기록 수정 |
| DELETE | `/api/memories/<id>/` | 기록 삭제 |
| POST | `/api/memories/<id>/images/` | 이미지 업로드 (multipart) |
| DELETE | `/api/memories/<id>/images/<image_id>/` | 이미지 삭제 |
| GET/POST | `/api/memories/categories/` | 카테고리 목록/생성 |
| PUT/DELETE | `/api/memories/categories/<id>/` | 카테고리 수정/삭제 |

**이미지 업로드 로직:**
- `multipart/form-data`로 `image` 필드 수신
- HEIC/HEIF 포맷은 서버에서 자동으로 JPEG 변환 (`pillow-heif`)
- 변환된 파일을 `media/memory_images/년/월/` 에 저장
- 개발 환경: Django가 직접 `/media/` URL로 서빙

---

### 📂 chat

**역할:** RAG 기반 AI 챗봇. 사용자 기록을 벡터 검색하여 Gemini로 응답 생성.

**비동기 임베딩:**
- `MemoryDetail` 저장 시 `signals.py`가 `embed_memory_task.delay()` 호출
- Celery worker가 백그라운드에서 Gemini API로 임베딩 생성 후 `content_embedding` 저장
- Redis DB 0을 브로커로 사용

---

## Serializer 구조

```
users/
  UserSerializer              — 유저 정보 읽기용

memories/
  MemoryListSerializer        — 목록/마커용 경량 (content 제외)
  MemoryDetailSerializer      — 상세용 (content, tags, images 포함)
  MemoryCreateSerializer      — 생성/수정 쓰기용
  MemoryImageSerializer       — 이미지 읽기용 (id, url, created_at)
  CategorySerializer          — 카테고리 CRUD
  TagSerializer               — 태그 읽기용
```

---

## 인증 방식

**JWT (djangorestframework-simplejwt)**

```
access token  → 유효기간 1h, 응답 body에 포함, 프론트 sessionStorage 저장
refresh token → 유효기간 7d, httpOnly 쿠키 (JS 접근 불가, XSS 차단)
```

**Redis 블랙리스트 (DB 3)**
- 로그아웃 시 access/refresh 두 토큰의 JTI를 TTL과 함께 `setex`
- `BlacklistAwareJWTAuthentication`이 매 요청마다 O(1) 조회

**레이트리밋 (DB 2)**
- DRF `AnonRateThrottle` / `UserRateThrottle` 카운터를 Redis에 저장
- 서버 재시작 시 카운터 초기화 방지

---

## 수직 파티셔닝 전략

```
GET /api/memories/         → Memory만 조회  (MemoryDetail JOIN 없음)
GET /api/memories/<id>/    → Memory + MemoryDetail JOIN (select_related)
```

목록 조회 시 무거운 `content`, `embedding` 컬럼을 건드리지 않아 대용량 성능 이점.

---

## 미디어 파일

| 항목 | 값 |
|------|-----|
| 저장 경로 | `Back_myArchive/media/memory_images/년/월/` |
| URL | `/media/memory_images/...` |
| 개발 서빙 | `config/urls.py`에서 `static()` 으로 Django가 직접 서빙 |
| HEIC 변환 | 업로드 시 `pillow-heif`로 자동 JPEG 변환 |

---

## 향후 확장

| 기능 | 방법 |
|------|------|
| 이미지 스토리지 | S3 연동 (`django-storages`) |
| 응답 캐싱 | Redis DB 1 캐시 레이어 추가 |
| 모니터링 | Sentry 연동 |
| 트랜잭션 | `transaction.atomic()` 적용 |
| 테스트 | pytest-django 기반 통합 테스트 작성 |

---

*최종 업데이트: 2026-04-14*
