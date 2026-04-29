# MyMemoryMap — Backend

지도 위에 장소와 감정을 기록하는 위치 기반 다이어리 앱의 백엔드.

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| Framework | Django 5.2 + Django REST Framework 3.17 |
| Database | PostgreSQL 14 + pgvector |
| Auth | JWT (djangorestframework-simplejwt) + Redis 블랙리스트 |
| Async | Celery + Redis (Gemini 임베딩 비동기 처리) |
| AI | Google Gemini (임베딩: gemini-embedding-001 / LLM: gemini-2.5-flash) |
| Deploy | Docker Compose (nginx + gunicorn + celery + redis + postgres) |

---

## ERD

```mermaid
erDiagram
    users {
        uuid id PK
        string email UK
        string username
        string nickname
        text profile_img_url
        datetime date_joined
    }

    address_regions {
        uuid id PK
        string province
        string city_district
        string town_neighborhood
        string admin_town
    }

    address_details {
        uuid id PK
        uuid region_id FK
        text road_address_name
        text address_name
        string main_address_no
        string sub_address_no
    }

    locations {
        uuid id PK
        uuid address_detail_id FK
        string kakao_place_id UK
        string place_name
        float latitude
        float longitude
        datetime created_at
    }

    categories {
        int id PK
        uuid user_id FK
        string name
        string color_code
    }

    memories {
        uuid id PK
        uuid user_id FK
        uuid location_id FK
        int category_id FK
        string title
        string mood
        string weather
        date visited_at
        datetime created_at
        datetime updated_at
    }

    memory_details {
        uuid memory_id PK_FK
        text content
        vector content_embedding
    }

    tags {
        uuid id PK
        uuid memory_id FK
        string name
    }

    memory_images {
        uuid id PK
        uuid memory_id FK
        string image
        datetime created_at
    }

    chat_sessions {
        uuid id PK
        uuid user_id FK
        text query_text
        text ai_response
        datetime created_at
    }

    users ||--o{ memories : ""
    users ||--o{ categories : ""
    users ||--o{ chat_sessions : ""
    address_regions ||--o{ address_details : ""
    address_details ||--o{ locations : ""
    locations ||--o{ memories : ""
    categories ||--o{ memories : ""
    memories ||--|| memory_details : ""
    memories ||--o{ tags : ""
    memories ||--o{ memory_images : ""
```

**설계 포인트**
- `Memory` + `MemoryDetail` 수직 파티셔닝 — 목록 조회 시 무거운 `content`, `embedding` 컬럼 건드리지 않음
- `AddressRegion → AddressDetail → Location` 3단계 정규화 — 행정구역 마스터 중복 저장 방지
- `content_embedding`: pgvector `VectorField(3072)` — Gemini 임베딩 저장, RAG 코사인 유사도 검색에 사용

---

## 로컬 실행

### Docker Compose (권장)

```bash
cp .env.example .env
# .env 수정 (SECRET_KEY, DB 비밀번호, GEMINI_API_KEY 등)

docker compose up -d
docker compose exec api python manage.py migrate
docker compose exec api python manage.py createsuperuser
```

`http://localhost:80` 으로 접근.

### 직접 실행 (개발)

**사전 조건:** PostgreSQL 14 + pgvector, Redis 설치

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env 수정

python manage.py migrate
python manage.py runserver

# 별도 터미널 — Celery worker
celery -A config worker --loglevel=info
```

`http://localhost:8000` 으로 접근.

---

## 환경변수

`.env.example` 참고.

| 변수 | 설명 | 예시 |
|------|------|------|
| `SECRET_KEY` | Django 시크릿 키 | `django-insecure-...` |
| `DEBUG` | 개발 모드 여부 | `True` |
| `ALLOWED_HOSTS` | 허용 호스트 | `localhost,127.0.0.1` |
| `DB_NAME` | DB 이름 | `mymemorymap` |
| `DB_USER` | DB 유저 | `dbuser` |
| `DB_PASSWORD` | DB 비밀번호 | — |
| `DB_HOST` | DB 호스트 | `localhost` |
| `DB_PORT` | DB 포트 | `5432` |
| `REDIS_URL` | Celery 브로커 (DB 0) | `redis://localhost:6379/0` |
| `REDIS_CACHE_URL` | 레이트리밋 카운터 (DB 2) | `redis://localhost:6379/2` |
| `REDIS_BLACKLIST_URL` | JWT 블랙리스트 (DB 3) | `redis://localhost:6379/3` |
| `GEMINI_API_KEY` | Google Gemini API 키 | — |

---

## RAG 구조

기록을 벡터로 저장해두고, 질문이 들어오면 유사한 기록을 찾아 Gemini에게 넘겨 답변을 생성하는 구조.

**참고:** [langchain-ai/langchain](https://github.com/langchain-ai/langchain) 기반으로 초기 구현 후, `task_type` 구분(`RETRIEVAL_DOCUMENT` / `RETRIEVAL_QUERY`) 지원을 위해 `google.genai` SDK 직접 호출로 전환.

### 임베딩 저장 흐름

```
POST /api/memories/
  → Memory + MemoryDetail 저장 → 즉시 201 반환
  → signals.py post_save 발화
  → embed_memory_task.delay()  (Celery 큐)
       ↓ 비동기
  → 제목 + 날짜 + 본문 합쳐서 텍스트 구성
  → Gemini embed_content(task_type=RETRIEVAL_DOCUMENT)
  → content_embedding 저장 (3072차원)
```

### 질문 응답 흐름

```
POST /api/chat/
  → 질문 텍스트 임베딩 (task_type=RETRIEVAL_QUERY)
  → pgvector CosineDistance로 내 기록 상위 5개 검색
  → distance > 0.5 제거 (무관한 기록 차단)
  → 남은 기록을 컨텍스트로 구성
  → Gemini generate_content 호출
  → 응답 + 출처(기록 제목/날짜/장소) 반환
```

### LangChain → google.genai 전환 내역

| 항목 | 초기 (LangChain) | 현재 (google.genai 직접) |
|------|-----------------|------------------------|
| 임베딩 모델 | `text-embedding-004` | `gemini-embedding-001` |
| 임베딩 차원 | 768 | 3072 |
| LLM 모델 | `gemini-1.5-flash` | `gemini-2.5-flash` |
| 임베딩 호출 | `GoogleGenerativeAIEmbeddings.embed_query()` | `client.models.embed_content()` + `task_type` 구분 |
| LLM 호출 | `ChatGoogleGenerativeAI.invoke([SystemMessage, HumanMessage])` | `client.models.generate_content()` |
| 유사도 필터 | 없음 | `distance > 0.5` 제거 |
| 레이트 리밋 | 없음 | `_retry_on_quota()` 자동 재시도 |

---

## API 문서

→ [docs/API.md](./docs/API.md)

Swagger UI (서버 실행 후): `http://localhost:8000/api/docs/`
