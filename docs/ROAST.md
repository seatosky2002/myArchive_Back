# 🔥 Backend Roast — MyMemoryMap

> 자동 코드 리뷰 결과. 프로덕션 배포 전 반드시 해결 필요.

---

## 🚨 CRITICAL

| # | 위치 | 문제 |
|---|------|------|
| 1 | `.env` | Gemini API 키 git 히스토리에 노출 → 즉시 revoke 필요 |
| 2 | `settings.py` | `DEBUG=True` 기본값 → SQL/스택트레이스/환경변수 전부 노출 |
| 3 | `chat/views.py` | `/api/chat/` 레이트 리밋 없음 → DoS 시 Gemini 비용 폭탄 |
| 4 | `seed_data.py` | `--email`, `--clear` 옵션이 인증 없이 타 유저 데이터 삭제/생성 가능 |

---

## ⚠️ MAJOR

| # | 위치 | 문제 |
|---|------|------|
| 5 | `memories/views.py` | 목록 API 페이지네이션 없음 → 전체 기록 한 번에 반환 |
| 6 | `memories/signals.py` | 임베딩 실패 시 조용히 넘어감 → RAG 검색에서 영원히 안 뜸 |
| 7 | `chat/services.py` | 관련 기록 0개여도 Gemini 호출 → 불필요한 API 비용 |
| 8 | `locations/serializers.py` | lat/lng 유효성 검사 없음 (위도 999 저장 가능) |
| 9 | `memories/views.py` | 검색 파라미터 길이 제한 없음 → DB 풀 스캔 가능 |
| 10 | `users/views.py` | DRF Token 만료 없음 → 한 번 탈취되면 영구 유효 |
| 11 | `memories/serializers.py` | Memory 생성 트랜잭션 없음 → Tag 실패 시 고아 레코드 |
| 12 | `migrations/` | 임베딩 차원 3번 변경 (1536→768→3072) → 이전 벡터와 호환 안 됨 |

---

## 📝 MINOR

| # | 위치 | 문제 |
|---|------|------|
| 13 | `locations/models.py` | `FloatField` 좌표 정밀도 오차 → `DecimalField` 권장 |
| 14 | `memories/models.py` | `Category.__str__` N+1 쿼리 (admin에서) |
| 15 | `memories/models.py` | `color_code` hex 형식 검증 없음 |
| 16 | `memories/models.py` | `visited_at`, `user` FK `db_index` 없음 |
| 17 | `*/tests.py` | 테스트 코드 전무 |
| 18 | `settings.py` | LOGGING 설정 없음 → 에러 로그 파일 안 남음 |
| 19 | `requirements.txt` | `numpy` import 어디서도 안 됨 (불필요한 의존성) |
| 20 | `memories/views.py` | 검색 Q객체 미사용 → 두 번 쿼리 후 `distinct()` |
| 21 | `users/models.py` | `profile_img_url` URL 형식 검증 없음 |
| 22 | `chat/services.py` | 모델명 하드코딩 → `.env`로 빼야 함 |

---

## ✅ 잘한 것

- 수직 파티셔닝 (`Memory` + `MemoryDetail`) 구조 탁월
- DRF Serializer List/Detail/Create 분리 잘 됨
- UUID PK 전반적으로 잘 사용
- pgvector 직접 소스 빌드해서 설치
- CORS 설정 올바르게 구성
- `select_related` / `prefetch_related` 적절히 사용

---

> 상세 설명 및 수정 방법 → [ROAST_DETAILS.md](./ROAST_DETAILS.md)
