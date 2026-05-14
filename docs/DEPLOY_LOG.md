# EC2 배포 트러블슈팅 로그

EC2 (t3.small, Ubuntu 24.04, 43.201.130.253) 첫 배포 시 발생한 문제와 해결책 정리.

---

## 1. `wait_for_db` 커맨드 없음

### 증상
```
api-1  | Unknown command: 'wait_for_db'
api-1  | Type 'manage.py help' for usage.
```
api 컨테이너가 재시작을 반복함.

### 원인
`entrypoint.sh`에서 `python manage.py wait_for_db`를 호출하는데,
이 커스텀 management command가 프로젝트에 구현되어 있지 않았음.

### 해결
`docker-compose.yml`에 이미 `depends_on: db: condition: service_healthy`로
DB 준비 대기가 설정되어 있으므로 `entrypoint.sh`에서 해당 줄 제거.

```bash
# entrypoint.sh 수정 후 push
git pull origin main
docker-compose up --build -d
```

---

## 2. pgvector extension 미활성화

### 증상
```
django.db.utils.ProgrammingError: type "vector" does not exist
LINE 1: ...content_embedding" vector(3072)...
```
`memories.0002_initial` migration 실패 → api 컨테이너 재시작 반복.

### 원인
`pgvector/pgvector:pg16` 이미지는 extension 바이너리만 포함하고,
DB에 실제로 `CREATE EXTENSION vector`를 실행해야 사용 가능함.
migration 파일에 이 과정이 없었음.

### 해결
**즉시 수동 활성화:**
```bash
docker-compose exec db psql -U $(grep DB_USER .env | cut -d= -f2) -d $(grep DB_NAME .env | cut -d= -f2) -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker-compose restart api
```

**영구 수정 (memories/migrations/0001_initial.py):**
```python
operations = [
    migrations.RunSQL(
        "CREATE EXTENSION IF NOT EXISTS vector;",
        reverse_sql="DROP EXTENSION IF EXISTS vector;",
    ),
    # ... 기존 operations
]
```
이후 fresh 배포 시에는 migration이 자동으로 extension을 활성화함.

---

## 3. gunicorn 미설치

### 증상
```
/entrypoint.sh: line 11: exec: gunicorn: not found
```
collectstatic은 성공했는데 서버 실행 단계에서 실패.

### 원인
`requirements.txt`에 `gunicorn`이 누락되어 있었음.

### 해결
`requirements.txt`에 추가:
```
gunicorn==23.0.0
```
push 후 EC2에서 rebuild:
```bash
git pull origin main
docker-compose up --build -d
```

---

## 4. 프론트엔드 빌드 파일 복사 권한 오류

### 증상
```
cp: cannot create regular file '...frontend/./index.html': Permission denied
```

### 원인
`frontend/` 디렉토리가 Docker에 의해 root 소유로 생성됨.

### 해결
```bash
sudo cp -r ~/Front_myArchive/dist/. ~/myArchive_Back/frontend/
sudo chown -R ubuntu:ubuntu ~/myArchive_Back/frontend/
```

---

## 5. GitHub clone 인증 실패

### 증상
```
remote: Invalid username or token. Password authentication is not supported.
fatal: Authentication failed
```

### 원인
GitHub은 2021년부터 HTTPS 비밀번호 인증을 차단함.
Personal Access Token(PAT) 또는 SSH key 필요.

### 해결
GitHub → Settings → Developer settings → Personal access tokens에서 PAT 발급 후:
```bash
git clone https://<PAT>@github.com/seatosky2002/Front_myArchive.git
```
> **주의:** PAT를 채팅/로그에 노출했다면 즉시 revoke 필요.

---

## 6. 빌드 후 styled-components 누락

### 증상
```
[vite]: Rollup failed to resolve import "styled-components"
Build failed
```

### 원인
`git pull` 후 `npm install`을 재실행하지 않아 의존성이 최신 `package.json`과 불일치.

### 해결
```bash
npm install && npm run build
sudo cp -r dist/. ~/myArchive_Back/frontend/
```

---

## 7. 로컬 DB → 서버 DB 이전

### 순서
```bash
# 1. 로컬 맥에서 dump
pg_dump -U byunmingyu -d mymemorymap -F c -f ~/mymemorymap_backup.dump

# 2. EC2로 전송
scp -i '/Users/byunmingyu/Downloads/Back_Archive.pem' ~/mymemorymap_backup.dump ubuntu@43.201.130.253:~/

# 3. EC2에서 — dump 파일을 DB 컨테이너로 복사
cd ~/myArchive_Back
docker cp ~/mymemorymap_backup.dump $(docker-compose ps -q db):/tmp/

# 4. restore
docker-compose exec db pg_restore -U byunmingyu -d mymemorymap --clean --if-exists /tmp/mymemorymap_backup.dump
```

### 주의
- `pg_restore` 명령어는 반드시 한 줄로 실행. 줄바꿈 포함 시 파일 경로가 별도 명령어로 인식되어 stdin 대기 상태에 빠짐.
- restore 성공 시 아무 출력 없음. `SELECT COUNT(*) FROM memories;` 로 확인.

---

## 8. SSH 접속 타임아웃

### 증상
```
ssh: connect to host 43.201.130.253 port 22: Operation timed out
```

### 원인
보안 그룹 인바운드 규칙에 SSH(22번)가 특정 IP만 허용되어 있었음. 현재 IP가 달라져서 막힘.

### 해결
AWS 콘솔 → 보안 그룹 → 인바운드 규칙 편집 → SSH 소스를 `0.0.0.0/0`으로 변경.

> 유동 IP 환경(카페, 집 공유기 재시작 등)에서는 IP가 수시로 바뀌므로 포트폴리오 수준에서는 전체 허용으로 운영.

---

## 9. 카카오맵 미표시 — IP 주소는 도메인 등록 불가

### 증상
카카오맵이 표시되지 않음.

### 원인
카카오 개발자 콘솔의 JavaScript SDK 도메인에 IP 주소(`http://43.201.130.253`)를 등록하면 "유효하지 않은 URL" 오류 발생. 카카오는 도메인만 허용.

### 해결
`nip.io` 무료 서비스 사용 — IP를 도메인처럼 쓸 수 있음.
- 등록 도메인: `http://43.201.130.253.nip.io`
- 접속 URL: `http://43.201.130.253.nip.io`

---

## 10. nip.io 접속 시 로그인 400 오류

### 증상
```
Failed to load resource: the server responded with a status of 400 (Bad Request) /api/users/login/
```

### 원인
`ALLOWED_HOSTS`에 nip.io 도메인이 없어 Django가 요청을 거부.

### 해결
`.env` 수정:
```
ALLOWED_HOSTS=43.201.130.253,43.201.130.253.nip.io
```
```bash
docker-compose up -d api
```

> **주의:** `docker-compose restart`는 컨테이너를 재시작만 하고 .env를 다시 읽지 않음.
> .env 변경사항 반영은 반드시 `docker-compose up -d`로 컨테이너를 새로 생성해야 함.

---

## 11. .env 수정 후 환경변수 미반영

### 증상
`.env`를 수정했는데 `settings.ALLOWED_HOSTS`에 변경사항이 없음.

### 원인
`docker-compose restart`는 컨테이너를 재시작만 할 뿐, 시작 시 메모리에 올라간 환경변수를 다시 읽지 않음.

### 해결
```bash
docker-compose up -d api
```
컨테이너를 새로 만들면서 .env를 다시 읽어옴.

---

## 12. DB 복원 후 비밀번호 불일치로 로그인 실패

### 증상
로컬 DB를 서버로 복원 후 로그인 시 400 오류.

### 원인
DB restore 시 비밀번호 해시도 복원되지만, 실제 평문 비밀번호를 모르는 경우 로그인 불가.

### 해결
EC2에서 비밀번호 강제 리셋:
```bash
docker-compose exec api python manage.py shell -c "from users.models import User; [setattr(u, 'password', None) or u.set_password('test1234') or u.save() for u in User.objects.all()]; print('done')"
```

---

## 정상 배포 최종 순서

```bash
# 백엔드 (EC2)
cd ~/myArchive_Back
git pull origin main
docker-compose up --build -d

# pgvector extension (최초 1회만)
docker-compose exec db psql -U $(grep DB_USER .env | cut -d= -f2) -d $(grep DB_NAME .env | cut -d= -f2) -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 프론트엔드 (EC2)
cd ~/Front_myArchive
git pull origin main
npm install
npm run build
sudo cp -r dist/. ~/myArchive_Back/frontend/
```
