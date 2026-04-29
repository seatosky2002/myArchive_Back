# MyMemoryMap API

Base URL: `http://localhost:8000/api`

---

## 인증

JWT 방식. 대부분의 엔드포인트는 `Authorization` 헤더 필요.

```
Authorization: Bearer <access_token>
```

| 토큰 | 위치 | 유효기간 |
|------|------|---------|
| access | 응답 body | 1시간 |
| refresh | httpOnly 쿠키 (`refresh`) | 7일 |

access 만료 시 → `POST /api/users/token/refresh/` 로 갱신 (쿠키 자동 전송).

**레이트 리밋**
- 일반 API: 200회/시간 (유저당)
- `/api/chat/`: 30회/시간 (유저당)

---

## 유저 `/api/users/`

### 회원가입
```
POST /api/users/register/
인증: 불필요
```

**요청**
```json
{
  "email": "user@example.com",
  "password": "password123",
  "nickname": "닉네임"
}
```

**응답 `201`**
```json
{
  "access": "<access_token>",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "nickname": "닉네임",
    "profile_img_url": null,
    "date_joined": "2026-04-29T00:00:00Z"
  }
}
```
+ `Set-Cookie: refresh=<refresh_token>; HttpOnly; Path=/api/users/token/`

---

### 로그인
```
POST /api/users/login/
인증: 불필요
```

**요청**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**응답 `200`** — 회원가입과 동일 구조

---

### 로그아웃
```
POST /api/users/logout/
인증: 필요
```

**응답 `200`**
```json
{ "detail": "로그아웃 되었습니다." }
```

access + refresh 토큰 모두 Redis 블랙리스트 등록. 쿠키 삭제.

---

### Access 토큰 갱신
```
POST /api/users/token/refresh/
인증: 불필요 (쿠키의 refresh 토큰 사용)
```

**응답 `200`**
```json
{ "access": "<new_access_token>" }
```
+ 새 refresh 쿠키 재설정 (rotation)

---

### 내 프로필 조회/수정
```
GET  /api/users/me/
PUT  /api/users/me/
인증: 필요
```

**PUT 요청** (변경할 필드만)
```json
{
  "nickname": "새닉네임",
  "profile_img_url": "https://..."
}
```

**응답 `200`**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "nickname": "닉네임",
  "profile_img_url": null,
  "date_joined": "2026-04-29T00:00:00Z"
}
```

---

## 장소 `/api/locations/`

### 장소 생성 또는 조회
```
POST /api/locations/
인증: 필요
```

`kakao_place_id`가 있으면 기존 장소 반환 (중복 저장 방지).

**요청**
```json
{
  "kakao_place_id": "12345678",
  "place_name": "경복궁",
  "latitude": 37.5796,
  "longitude": 126.9770,
  "province": "서울특별시",
  "city_district": "종로구",
  "town_neighborhood": "세종로",
  "road_address_name": "서울 종로구 사직로 161",
  "address_name": "서울 종로구 세종로 1-1"
}
```

필수: `place_name`, `latitude`, `longitude`
선택: 나머지 (카카오 장소 검색 API 응답 필드)

**응답 `201`**
```json
{
  "id": "uuid",
  "kakao_place_id": "12345678",
  "place_name": "경복궁",
  "road_address": "서울 종로구 사직로 161",
  "address": "서울 종로구 세종로 1-1",
  "latitude": 37.5796,
  "longitude": 126.9770
}
```

---

### 장소 상세 조회
```
GET /api/locations/<id>/
인증: 필요
```

**응답 `200`** — 위와 동일 구조

---

## 기록 `/api/memories/`

### 기록 목록 조회
```
GET /api/memories/
인증: 필요
```

**쿼리 파라미터**
| 파라미터 | 설명 |
|---------|------|
| `page` | 페이지 번호 (기본 1) |
| `page_size` | 페이지 크기 (기본 50, 최대 200) |
| `search` | 제목 또는 태그명 검색 (최대 100자) |

**응답 `200`**
```json
{
  "count": 500,
  "next": "http://localhost:8000/api/memories/?page=2",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "title": "경복궁 산책",
      "mood": "peaceful",
      "mood_display": "평온한",
      "weather": "sunny",
      "weather_display": "맑음",
      "visited_at": "2026-04-29",
      "created_at": "2026-04-29T12:00:00Z",
      "location": {
        "id": "uuid",
        "place_name": "경복궁",
        "road_address": "서울 종로구 사직로 161",
        "address": "서울 종로구 세종로 1-1",
        "latitude": 37.5796,
        "longitude": 126.9770
      },
      "category": null,
      "tags": ["산책", "봄", "서울"]
    }
  ]
}
```

content(본문) 제외 — 지도 마커/사이드바용 경량 응답.

---

### 기록 생성
```
POST /api/memories/
인증: 필요
```

**요청**
```json
{
  "title": "경복궁 산책",
  "mood": "peaceful",
  "weather": "sunny",
  "visited_at": "2026-04-29",
  "location_id": "uuid",
  "category_id": null,
  "content": "오늘은 날씨가 정말 좋았다...",
  "tags": ["산책", "봄", "서울"]
}
```

**mood 값:** `happy` `peaceful` `excited` `sad` `angry` `anxious` `tired` `grateful`

**weather 값:** `sunny` `cloudy` `rainy` `snowy` `windy` `foggy` `sunrise` `stormy`

**응답 `201`** — 기록 상세 응답 구조 (아래 참고)

---

### 기록 상세 조회
```
GET /api/memories/<id>/
인증: 필요
```

**응답 `200`**
```json
{
  "id": "uuid",
  "title": "경복궁 산책",
  "mood": "peaceful",
  "mood_display": "평온한",
  "weather": "sunny",
  "weather_display": "맑음",
  "visited_at": "2026-04-29",
  "created_at": "2026-04-29T12:00:00Z",
  "updated_at": "2026-04-29T12:00:00Z",
  "location": { ... },
  "category": null,
  "tags": [
    { "id": 1, "name": "산책" }
  ],
  "images": [
    { "id": "uuid", "url": "/media/memory_images/2026/04/xxx.jpg", "created_at": "..." }
  ],
  "content": "오늘은 날씨가 정말 좋았다..."
}
```

---

### 기록 수정
```
PUT /api/memories/<id>/
인증: 필요
```

요청/응답 구조 — 기록 생성과 동일. 변경할 필드만 전송 가능 (partial).

---

### 기록 삭제
```
DELETE /api/memories/<id>/
인증: 필요
```

**응답 `204`** (No Content)

MemoryDetail, Tag, Image 모두 CASCADE 삭제.

---

### 이미지 업로드
```
POST /api/memories/<id>/images/
인증: 필요
Content-Type: multipart/form-data
```

**요청**
```
image: <파일>
```

HEIC/HEIF 포맷은 서버에서 JPEG로 자동 변환.

**응답 `201`**
```json
{
  "id": "uuid",
  "url": "/media/memory_images/2026/04/xxx.jpg",
  "created_at": "2026-04-29T12:00:00Z"
}
```

---

### 이미지 삭제
```
DELETE /api/memories/<id>/images/<image_id>/
인증: 필요
```

**응답 `204`** (No Content)

파일 + DB 레코드 모두 삭제.

---

## 카테고리 `/api/memories/categories/`

### 카테고리 목록 / 생성
```
GET  /api/memories/categories/
POST /api/memories/categories/
인증: 필요
```

**POST 요청**
```json
{
  "name": "여행",
  "color_code": "#4D7C0F"
}
```

**응답**
```json
[
  { "id": 1, "name": "여행", "color_code": "#4D7C0F" }
]
```

---

### 카테고리 수정 / 삭제
```
PUT    /api/memories/categories/<id>/
DELETE /api/memories/categories/<id>/
인증: 필요
```

삭제 시 해당 카테고리의 기록들은 `category = null` 처리 (기록 삭제 없음).

---

## 채팅 `/api/chat/`

RAG 기반 AI 챗봇. 내 기록을 벡터 검색하여 Gemini가 응답 생성.

**레이트 리밋: 30회/시간**

### 질문하기
```
POST /api/chat/
인증: 필요
```

**요청**
```json
{
  "message": "내가 제일 자주 간 카페가 어디야?"
}
```

**응답 `200`**
```json
{
  "response": "가장 자주 방문한 카페는 '서울대입구 스타벅스'입니다. 총 7번 기록되었으며...",
  "sources": [
    {
      "title": "스타벅스에서 공부",
      "visited_at": "2026-03-10",
      "place_name": "스타벅스 서울대입구점",
      "distance": 0.12
    }
  ]
}
```

`distance`: 코사인 유사도 기반 거리 (0에 가까울수록 관련성 높음)

---

### 대화 기록 조회
```
GET /api/chat/history/
인증: 필요
```

**응답 `200`**
```json
[
  {
    "id": "uuid",
    "query_text": "내가 제일 자주 간 카페가 어디야?",
    "ai_response": "가장 자주 방문한 카페는...",
    "created_at": "2026-04-29T12:00:00Z"
  }
]
```

최근 20개 반환.

---

## 에러 응답

| 상태코드 | 의미 |
|---------|------|
| `400` | 잘못된 요청 (유효성 검사 실패) |
| `401` | 인증 실패 또는 토큰 만료 |
| `404` | 리소스 없음 (타인 리소스 접근 포함) |
| `429` | 레이트 리밋 초과 |

```json
{ "detail": "에러 메시지" }
```
