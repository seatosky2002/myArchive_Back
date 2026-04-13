"""
DB가 준비될 때까지 대기하는 커맨드.
Docker Compose에서 api/worker 컨테이너가 db healthcheck를 통과해도
PostgreSQL이 실제 연결을 받을 준비가 안 됐을 수 있음.
"""
import time
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = 'DB가 응답할 때까지 대기'

    def handle(self, *args, **options):
        self.stdout.write('DB 대기 중...')
        for attempt in range(30):
            try:
                connections['default'].ensure_connection()
                self.stdout.write(self.style.SUCCESS('DB 연결 성공'))
                return
            except OperationalError:
                self.stdout.write(f'  {attempt + 1}/30 대기 중...')
                time.sleep(2)
        raise SystemExit('DB 연결 실패 (30회 시도)')
