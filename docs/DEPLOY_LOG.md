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
