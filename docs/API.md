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

| 엔드포인트 | 제한 | 기준 |
|-----------|------|------|
| `/api/users/login/` | 5회/분 | IP |
| `/api/users/register/` | 3회/분 | IP |
| `/api/chat/` | 500회/시간 | 유저 |
| 나머지 전체 | 10,000회/시간 | 유저 |

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
+ 새 refresh 쿠키 재설정 (rotation — 구 refresh JTI 블랙리스트 등록)

---

### 내 프로필 조회 / 수정
```
GET /api/users/me/
PUT /api/users/me/
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

`kakao_place_id`가 동일한 장소가 이미 존재하면 새로 생성하지 않고 기존 레코드 반환.

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
GET /api/locations/<uuid:id>/
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

개인 기록만 반환 (`group = null`). 그룹 기록은 `GET /api/groups/<id>/memories/` 에서 조회.

**쿼리 파라미터**

| 파라미터 | 설명 |
|---------|------|
| `page` | 페이지 번호 (기본 1) |
| `page_size` | 페이지 크기 (기본 50, 최대 200) |
| `search` | 제목 또는 태그명 검색 (최대 100자) |

**응답 `200`**
```json
{
  "count": 42,
  "next": "http://localhost:8000/api/memories/?page=2",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "group_id": null,
      "author_nickname": "닉네임",
      "title": "경복궁 산책",
      "mood": "peaceful",
      "mood_display": "평화로운",
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
      "tags": ["산책", "봄", "서울"],
      "images": [
        { "id": "uuid", "url": "/media/memory_images/2026/04/xxx.jpg", "created_at": "..." }
      ]
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
  "group_id": null,
  "content": "오늘은 날씨가 정말 좋았다...",
  "tags": ["산책", "봄", "서울"]
}
```

**mood 값:** `peaceful` `happy` `calm` `energetic` `sad` `excited`

**weather 값:** `sunny` `cloudy` `rainy` `snowy` `night` `sunrise`

`group_id` 전달 시 그룹 기록으로 생성. 해당 그룹의 활성 멤버여야 하며 `viewer` 역할은 생성 불가.

**응답 `201`** — 기록 상세 응답 구조 (아래 참고)

---

### 기록 상세 조회
```
GET /api/memories/<uuid:id>/
인증: 필요
```

본인 기록이거나 같은 그룹의 활성 멤버면 조회 가능. 그 외 `404`.

**응답 `200`**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "group_id": null,
  "author_nickname": "닉네임",
  "title": "경복궁 산책",
  "mood": "peaceful",
  "mood_display": "평화로운",
  "weather": "sunny",
  "weather_display": "맑음",
  "visited_at": "2026-04-29",
  "created_at": "2026-04-29T12:00:00Z",
  "updated_at": "2026-04-29T12:00:00Z",
  "location": { "...": "..." },
  "category": null,
  "tags": [
    { "id": "uuid", "name": "산책" }
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
PUT /api/memories/<uuid:id>/
인증: 필요
```

본인 기록만 수정 가능. 변경할 필드만 전송 가능 (partial). 요청/응답 구조는 기록 생성과 동일.

---

### 기록 삭제
```
DELETE /api/memories/<uuid:id>/
인증: 필요
```

본인 기록 또는 그룹 `admin`/`owner`가 삭제 가능. 그룹 admin이 타인 기록 삭제 시 `GroupActivity` 로그 기록.

**응답 `204`** (No Content)

MemoryDetail, Tag, Image 모두 CASCADE 삭제.

---

### 이미지 업로드
```
POST /api/memories/<uuid:id>/images/
인증: 필요
Content-Type: multipart/form-data
```

본인 기록에만 업로드 가능.

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
DELETE /api/memories/<uuid:id>/images/<uuid:image_id>/
인증: 필요
```

**응답 `204`** (No Content). 파일 + DB 레코드 모두 삭제.

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

**GET 응답 `200`**
```json
[
  { "id": 1, "name": "여행", "color_code": "#4D7C0F" }
]
```

---

### 카테고리 수정 / 삭제
```
PUT    /api/memories/categories/<int:id>/
DELETE /api/memories/categories/<int:id>/
인증: 필요
```

삭제 시 해당 카테고리의 기록들은 `category = null` 처리 (기록 삭제 없음).

---

## 그룹 `/api/groups/`

### 내 그룹 목록 조회
```
GET /api/groups/
인증: 필요
```

활성 멤버(`status=active`)로 참여 중인 그룹만 반환.

**응답 `200`**
```json
[
  {
    "id": "uuid",
    "name": "우리 팀 여행",
    "description": "팀 워크샵 기록",
    "cover_img_url": null,
    "invite_code": "abc123XY",
    "max_members": 20,
    "my_role": "owner",
    "member_count": 3,
    "created_at": "2026-04-29T12:00:00Z"
  }
]
```

---

### 그룹 생성
```
POST /api/groups/
인증: 필요
```

**요청**
```json
{
  "name": "우리 팀 여행",
  "description": "팀 워크샵 기록",
  "cover_img_url": null,
  "max_members": 20
}
```

**응답 `201`** — 그룹 목록 조회와 동일 구조. 생성자는 자동으로 `owner`로 등록.

---

### 초대 코드로 그룹 가입
```
POST /api/groups/join/
인증: 필요
```

**요청**
```json
{
  "invite_code": "abc123XY"
}
```

**응답 `200`** — 가입한 그룹 정보 반환 (그룹 목록 조회와 동일 구조)

| 케이스 | 결과 |
|--------|------|
| 처음 가입 | `GroupMember` 생성 (`role=member`, `status=active`) |
| 이전에 탈퇴한 경우 | 기존 레코드 `status=active`로 복구 |
| 이미 활성 멤버 | `400` |
| 추방된 멤버 | `403` |
| 정원 초과 | `400` |

---

### 그룹 상세 조회
```
GET /api/groups/<uuid:id>/
인증: 필요
```

해당 그룹의 활성 멤버만 조회 가능.

**응답 `200`**
```json
{
  "id": "uuid",
  "name": "우리 팀 여행",
  "description": "팀 워크샵 기록",
  "cover_img_url": null,
  "invite_code": "abc123XY",
  "max_members": 20,
  "my_role": "owner",
  "member_count": 3,
  "created_at": "2026-04-29T12:00:00Z",
  "updated_at": "2026-04-29T12:00:00Z"
}
```

---

### 그룹 수정
```
PATCH /api/groups/<uuid:id>/
인증: 필요 (admin 이상)
```

**요청** (변경할 필드만)
```json
{
  "name": "새 그룹 이름",
  "description": "새 설명",
  "max_members": 30
}
```

**응답 `200`** — 그룹 상세 조회와 동일 구조

---

### 그룹 삭제
```
DELETE /api/groups/<uuid:id>/
인증: 필요 (owner만)
```

soft delete (`deleted_at` 설정). 그룹 내 기록은 보존.

**응답 `204`** (No Content)

---

### 멤버 목록 조회
```
GET /api/groups/<uuid:id>/members/
인증: 필요 (활성 멤버)
```

**응답 `200`**
```json
[
  {
    "id": "uuid",
    "user": {
      "id": "uuid",
      "nickname": "닉네임",
      "profile_img_url": null
    },
    "role": "owner",
    "status": "active",
    "joined_at": "2026-04-29T12:00:00Z"
  }
]
```

**role 값:** `owner` `admin` `member` `viewer`

---

### 멤버 역할 변경
```
PATCH /api/groups/<uuid:id>/members/<uuid:user_id>/
인증: 필요 (admin 이상)
```

`owner` 역할은 변경 불가.

**요청**
```json
{
  "role": "admin"
}
```

**응답 `200`** — 변경된 멤버 정보 반환

---

### 멤버 추방
```
DELETE /api/groups/<uuid:id>/members/<uuid:user_id>/
인증: 필요 (admin 이상)
```

`owner`는 추방 불가. 추방된 멤버는 `status=banned` 처리되어 초대 코드로 재가입 불가.

**응답 `204`** (No Content)

---

### 그룹 탈퇴
```
POST /api/groups/<uuid:id>/leave/
인증: 필요
```

`owner`는 탈퇴 불가 (그룹 삭제 또는 owner 양도 필요).

**응답 `204`** (No Content)

---

### 초대 코드 재발급
```
POST /api/groups/<uuid:id>/reset-invite-code/
인증: 필요 (admin 이상)
```

기존 초대 코드 즉시 무효화 후 새 코드 발급.

**응답 `200`**
```json
{
  "invite_code": "newXY123"
}
```

---

### 그룹 기록 목록 조회
```
GET /api/groups/<uuid:id>/memories/
인증: 필요 (활성 멤버)
```

해당 그룹에 속한 기록 전체 반환. 응답 구조는 `GET /api/memories/`와 동일 (페이지네이션 포함).

**쿼리 파라미터**

| 파라미터 | 설명 |
|---------|------|
| `page` | 페이지 번호 (기본 1) |
| `page_size` | 페이지 크기 (기본 50, 최대 200) |

---

## 채팅 `/api/chat/`

RAG 기반 AI 챗봇. 내 기록을 pgvector로 검색하여 Gemini가 응답 생성.  
**레이트 리밋: 500회/시간**

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

`distance`: 코사인 거리 (0에 가까울수록 관련성 높음). `0.5` 초과 기록은 컨텍스트에서 제외.

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
| `403` | 권한 없음 |
| `404` | 리소스 없음 (타인 리소스 접근 포함) |
| `429` | 레이트 리밋 초과 |

```json
{ "detail": "에러 메시지" }
```
