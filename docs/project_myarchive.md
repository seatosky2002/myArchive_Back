---
name: MyArchive 프로젝트 개요
description: MyMemoryMap — 위치 기반 일기 앱. 백엔드(Django+DRF), 프론트(React+Vite), RAG 챗봇(Gemini) 구조.
type: project
originSessionId: b374dda0-da6b-44c4-b1b3-e0474cea40c7
---
위치 기반 일기 앱. 지도 위에 기록을 마커로 표시하고 AI 챗봇으로 기억을 검색하는 서비스.

**Why:** 개인 프로젝트 / 포트폴리오
**How to apply:** 이 프로젝트 작업 시 백/프론트 구조 및 API 계약 파악에 활용

## 디렉토리 구조
- 백엔드: `/Users/byunmingyu/Desktop/myArchive/Back_myArchive/`
- 프론트: `/Users/byunmingyu/Desktop/myArchive/Front/Front_myArchive/`

## 백엔드 스택
- Django 5.2 + DRF 3.17
- PostgreSQL 14 + pgvector (벡터 검색)
- JWT 인증 (simplejwt) — access 1h body / refresh 7d httpOnly 쿠키
- Redis DB 0: Celery 브로커 / DB 2: 레이트 리밋 / DB 3: JWT 블랙리스트
- Celery: Gemini 임베딩 비동기 처리
- Gemini API: gemini-embedding-001 (3072차원) + gemini-2.5-flash

## 프론트 스택
- React 19 + Vite 7 + styled-components
- Kakao Maps API (CDN)
- axios (client.js에서 Bearer 헤더 자동 부착 + 401 시 refresh 재발급)

## 백엔드 앱 구성
- `users/`: JWT 인증, 블랙리스트 (Redis), 프로필
- `locations/`: 카카오 장소 → AddressRegion → AddressDetail → Location 3단계 정규화
- `memories/`: Memory (경량 메타) + MemoryDetail (본문+벡터) 수직 파티셔닝, Tag, Category, MemoryImage
- `chat/`: RAG 챗봇 (pgvector 코사인 유사도 검색 → Gemini 생성)

## RAG 흐름
1. 기록 저장 → signals.py → Celery `embed_memory_task.delay()` → Gemini embedding → content_embedding 저장
2. 챗 질문 → 질문 임베딩 → pgvector CosineDistance 검색 (상위 5, distance≤0.5) → Gemini generate_content → 응답+sources 반환

## 주요 API 엔드포인트
- POST /api/users/login/ — {access} body + refresh 쿠키
- POST /api/users/token/refresh/ — 쿠키 refresh → 새 access
- POST /api/locations/ — kakao_place_id 기준 dedup
- GET/POST /api/memories/ — 경량 목록(페이지네이션 50개) / 생성
- GET/PUT/DELETE /api/memories/<id>/ — 상세/수정/삭제
- POST /api/memories/<id>/images/ — 이미지 업로드 (HEIC→JPEG 자동 변환)
- POST /api/chat/ — RAG 응답 {response, sources}
- GET /api/chat/history/ — 최근 20개

## 프론트 핵심 구조
- App.jsx: useAuth + useEntries + useUIState 조합
- useEntries: toEntry()로 백엔드↔프론트 스키마 변환 (visited_at→date, place_name→location.name 등)
- client.js: 401→refresh 재발급 큐 패턴 (isRefreshing + pendingQueue)

## 알려진 이슈 (ROAST)
- 백: Memory 생성에 transaction.atomic() 없음, lat/lng 유효성 검사 없음
- 프론트: XSS 이슈 수정됨(textContent 사용), 401 처리 개선됨(refresh 큐 패턴)
- ROAST_DETAILS.md에 상세 수정 방법 기록됨

## EC2 배포 현황 (2026-05-17 기준)
- 서버: AWS EC2 t3.micro (ip: 43.201.130.253, RAM 1.86GB, vCPU 2개)
- 접속 URL: http://43.201.130.253.nip.io (카카오 SDK 도메인 허용 때문에 nip.io 사용)
- PEM 키: /Users/byunmingyu/Downloads/Back_Archive.pem
- 서버 디렉토리: /home/ubuntu/myArchive_Back/
- DB: EC2 내부에 PostgreSQL 컨테이너로 운영 (RDS 미사용)
- 서버 계정: seatosky2002@naver.com, test@mymemorymap.com (비밀번호 test1234), loadtest@test.com (비밀번호 Test1234!)
- .env 주요 변수: DB_USER=byunmingyu, DB_NAME=mymemorymap, ALLOWED_HOSTS=43.201.130.253,43.201.130.253.nip.io
- 배포 이슈 로그: Back_myArchive/docs/DEPLOY_LOG.md

## 프론트엔드 배포 방식
- 프론트는 git에서 제외됨 (.gitignore에 frontend/ 등록)
- 배포 순서: 로컬에서 `npm run build` → `sudo cp -r dist/* ~/myArchive_Back/frontend/` (EC2에서)
- nginx가 /app/frontend를 볼륨 마운트로 서빙 (재시작 불필요)
- EC2에 ~/Front_myArchive 별도 존재 → 거기서 git pull + npm run build

## Docker 운영 주의사항
- docker-compose (하이픈) 사용 — EC2에 Compose v2 미설치
- .env 수정 후 반드시 `docker-compose up -d` (restart는 .env 미반영)
- 환경변수 확인: `docker-compose exec api python manage.py shell -c "from django.conf import settings; print(settings.ALLOWED_HOSTS)"`
- 카카오 JS SDK 키: 7e3d6b22b33faa17dac9480740b60148 (nip.io 도메인 등록됨)
- Gunicorn 워커: 4개 gevent 워커 (docker-compose.yml에서 설정, sync→gevent 전환 완료)

## 부하 테스트 결과 (2026-05-17)
- 도구: locust, locustfile 위치: /Users/byunmingyu/Desktop/myArchive/locustfile.py
- 테스트 계정: test@mymemorymap.com / test1234
- 동시 50명 기준: 에러율 0%, 평균 응답시간 17초 (정상 기준 200ms)
- 병목: Gunicorn sync 워커 4개 큐 대기 (DB는 CPU 1.3%, 메모리 2%로 문제 없음)
- 원인: sync 워커 4개로 50명 처리 시 46명이 큐 대기 → 10ms DB 쿼리가 17,000ms 응답으로
- CONN_MAX_AGE=60 배포 완료 (CI/CD로 자동 배포됨)
- 로그인 Throttle: 5/minute (locust에서 토큰 1개 공유 방식으로 우회)
- Gunicorn gevent 워커 전환 완료 (2026-05-17)
- 포트폴리오 스토리: 부하테스트 → DB 벤치마크로 DB 무죄 확인 → Gunicorn 워커 한계 특정 → gevent 해결

## POST /api/memories/ 병목 조사 (2026-05-19)
- 현상: 50명 기준 POST /api/memories/ 중간값 31초, 최솟값 22초
- 가설: gevent 환경에서 Celery embed_memory_task.delay() 호출 시 Redis 연결 블로킹
- 검증: signals.py에서 delay() 임시 skip → POST 중간값 31초 → 2.8초로 감소 확인
- 원인 확정: gevent worker + redis-py 조합에서 .delay() 호출이 블로킹
- 해결 방향: gevent-safe Redis 연결 (gevent monkey-patch 적용 시점 조정 또는 gevent 호환 Celery 브로커 설정)

## DB 쿼리 벤치마크 (2026-05-17, 기록 1,243건 기준)
- Memory 목록 50개: 7.7ms
- Memory 목록 page2: 4.9ms
- Memory 상세 1건: 2.5ms
- MemoryDetail 조회 50개: 25.7ms
- Memory 전체 카운트: 1.6ms
- pgvector 코사인 유사도 검색 top5: 83.9ms (인덱스 없이 순차 스캔)
- 벤치마크 스크립트: /Users/byunmingyu/Desktop/myArchive/db_benchmark.py
- pgvector HNSW 인덱스 추가 시 84ms → 5~10ms 예상
