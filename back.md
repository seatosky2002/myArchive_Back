# MyMemoryMap — 백엔드 구조 문서

## 기술 스택

| 항목 | 내용 |
|------|------|
| Framework | Django 5.2 + Django REST Framework 3.17 |
| Database | PostgreSQL + pgvector |
| Auth | Django 세션 인증 (추후 JWT 전환 가능) |
| Python | 3.10 |

---

## 프로젝트 구조

```
Back_myArchive/
├── config/
│   ├── settings.py     # 환경변수, 앱 등록, DB 연결, DRF 설정
│   └── urls.py         # 루트 URL (각 앱 urls.py로 위임)
├── users/              # 사용자 인증 및 프로필
├── locations/          # 주소 정규화 및 장소 관리
├── memories/           # 기록 CRUD, 태그, 카테고리, AI 벡터
└── requirements.txt
```

---

## 앱별 역할

### 📂 users

**역할:** 회원가입, 로그인, 로그아웃, 내 프로필 조회/수정

**모델:** `User` (AbstractUser 상속, UUID PK, email 로그인)

**엔드포인트:**

| Method | URL | 설명 |
|--------|-----|------|
| POST | `/api/users/register/` | 회원가입 |
| POST | `/api/users/login/` | 로그인 (세션) |
| POST | `/api/users/logout/` | 로그아웃 |
| GET/PUT | `/api/users/me/` | 내 프로필 조회/수정 |

**뷰 로직:**
- `RegisterView`: email, password, nickname 받아 User 생성. 생성 후 자동 로그인.
- `LoginView`: email + password로 authenticate() → login() → 세션 발급.
- `LogoutView`: Django logout() 호출로 세션 삭제.
- `MeView`: 요청한 유저(request.user) 본인 정보만 조회/수정.

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

**뷰 로직:**
- `LocationCreateView (POST)`:
  1. `kakao_place_id`가 있으면 기존 Location 반환 (중복 저장 방지).
  2. 없으면 province/city_district/town_neighborhood로 `AddressRegion` get_or_create.
  3. road_address/lot_address로 `AddressDetail` get_or_create.
  4. `Location` 신규 생성.
  - 프론트에서 카카오 API 응답을 그대로 전달하면 백엔드가 정규화 처리.

---

### 📂 memories

**역할:** 기록 CRUD. 목록(경량)과 상세(중량)를 분리 조회. 카테고리, 태그 관리.

**모델:**
- `Memory`: 경량 메타 (제목, 무드, 날씨, 날짜, 위치)
- `MemoryDetail`: 중량 본문 + AI 벡터 (1:1 수직 파티셔닝)
- `Category`: 사용자별 카테고리
- `Tag`: 기록별 태그 (unique per memory)
- `MemoryImage`: 첨부 이미지
- `ChatSession`: AI 채팅 기록

**엔드포인트:**

| Method | URL | 설명 |
|--------|-----|------|
| GET | `/api/memories/` | 기록 목록 (경량 — 지도 마커/사이드바용) |
| POST | `/api/memories/` | 기록 생성 |
| GET | `/api/memories/<id>/` | 기록 상세 (본문 포함) |
| PUT/PATCH | `/api/memories/<id>/` | 기록 수정 |
| DELETE | `/api/memories/<id>/` | 기록 삭제 |
| GET/POST | `/api/memories/categories/` | 카테고리 목록/생성 |
| PUT/DELETE | `/api/memories/categories/<id>/` | 카테고리 수정/삭제 |

**뷰 로직:**

- `MemoryListCreateView (GET)`:
  - `request.user` 기준 본인 기록만 반환.
  - `MemoryListSerializer` 사용 (content 제외, 경량).
  - 쿼리파라미터: `?search=키워드` (제목/태그 필터링).

- `MemoryListCreateView (POST)`:
  1. `MemoryCreateSerializer`로 유효성 검사.
  2. `Memory` 저장 후 `MemoryDetail` (content) 함께 저장.
  3. 태그 배열 받아 `Tag` bulk_create.
  4. 저장된 기록 반환.

- `MemoryDetailView (GET)`:
  - `MemoryDetailSerializer` 사용 (content, 태그, 이미지 포함).
  - 본인 기록이 아니면 403.

- `MemoryDetailView (PUT/PATCH)`:
  - Memory + MemoryDetail 동시 업데이트.
  - 태그: 기존 삭제 후 새로 bulk_create.

- `MemoryDetailView (DELETE)`:
  - CASCADE로 MemoryDetail, Tag, Image 자동 삭제.

---

## Serializer 구조

```
users/
  UserSerializer          — 유저 정보 읽기용
  RegisterSerializer      — 회원가입 쓰기용 (password hashing)
  LoginSerializer         — 로그인 유효성 검사

locations/
  LocationSerializer      — 장소 읽기용
  LocationCreateSerializer — 장소 생성 (카카오 API 응답 필드 수용)

memories/
  MemoryListSerializer    — 목록/마커용 경량 (content 제외)
  MemoryDetailSerializer  — 상세용 (content, tags, images 포함)
  MemoryCreateSerializer  — 생성/수정 쓰기용
  CategorySerializer      — 카테고리 CRUD
  TagSerializer           — 태그 읽기용
```

---

## 인증 방식

현재: Django 세션 인증 (`SessionAuthentication`)
- 로그인 → 서버가 세션 쿠키 발급
- 이후 요청마다 쿠키 자동 포함

추후 전환 가능: JWT (`djangorestframework-simplejwt`)
- `settings.py`의 `DEFAULT_AUTHENTICATION_CLASSES`만 변경하면 됨

---

## 수직 파티셔닝 전략

```
GET /api/memories/         → Memory만 조회  (MemoryDetail JOIN 없음)
GET /api/memories/<id>/    → Memory + MemoryDetail JOIN (select_related)
```

목록 조회 시 무거운 content, embedding 컬럼을 아예 건드리지 않아 대용량에서 성능 이점.

---

## 향후 확장

| 기능 | 방법 |
|------|------|
| AI 검색 | MemoryDetail.content_embedding에 OpenAI 임베딩 저장 후 pgvector 코사인 유사도 검색 |
| JWT 인증 | simplejwt 패키지로 교체 |
| 이미지 업로드 | S3 또는 로컬 스토리지 연동 |
| 카테고리 필터 | GET /api/memories/?category=<id> 쿼리파라미터 추가 |

---

*최종 업데이트: 2026-03-25*
