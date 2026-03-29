"""
embed_memories.py — 기존 기록 일괄 임베딩

사용법:
    python manage.py embed_memories                     # 전체 미임베딩 기록
    python manage.py embed_memories --email test@...    # 특정 유저만
    python manage.py embed_memories --all               # 전체 재임베딩 (기존 덮어쓰기)
"""
import time
from django.core.management.base import BaseCommand
from memories.models import MemoryDetail
from chat.services import embed_memory


class Command(BaseCommand):
    help = 'content_embedding이 없는 기록을 Gemini로 일괄 임베딩'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='특정 유저 이메일만 처리')
        parser.add_argument('--all',   action='store_true', help='이미 임베딩된 것도 재처리')

    def handle(self, *args, **options):
        qs = MemoryDetail.objects.select_related('memory', 'memory__user')

        if options['email']:
            qs = qs.filter(memory__user__email=options['email'])

        if not options['all']:
            qs = qs.filter(content_embedding__isnull=True)

        total = qs.count()
        if total == 0:
            self.stdout.write('임베딩할 기록이 없습니다.')
            return

        self.stdout.write(f'{total}개 기록 임베딩 시작...')
        success, fail = 0, 0

        for i, md in enumerate(qs.iterator(), start=1):
            try:
                embed_memory(md)
                success += 1
            except Exception as e:
                fail += 1
                self.stdout.write(self.style.WARNING(f'  실패 (id={md.memory_id}): {e}'))

            if i % 50 == 0:
                self.stdout.write(f'  {i}/{total} 처리 중...')

            # Gemini API rate limit 방지
            time.sleep(0.1)

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ 완료! 성공: {success}개 / 실패: {fail}개'
        ))
