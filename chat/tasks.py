"""
chat/tasks.py — Celery 비동기 태스크

embed_memory_task: 기록 저장 후 Gemini 임베딩을 백그라운드에서 처리.
  - 기록 저장 API가 Gemini 응답을 기다리지 않아도 됨 → 즉각 201 응답
  - 실패 시 60초 간격으로 최대 3회 자동 재시도
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='chat.tasks.embed_memory_task',
)
def embed_memory_task(self, memory_detail_id):
    from memories.models import MemoryDetail
    from chat.services import embed_memory

    try:
        md = MemoryDetail.objects.select_related('memory').get(pk=memory_detail_id)
        embed_memory(md)
        logger.info(f'임베딩 완료: memory_id={memory_detail_id}')
    except Exception as exc:
        logger.error(f'임베딩 실패 (시도 {self.request.retries + 1}/3) memory_id={memory_detail_id}: {exc}')
        raise self.retry(exc=exc)
