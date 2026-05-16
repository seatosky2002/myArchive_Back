"""
memories/signals.py — 기록 저장 시 자동 임베딩

MemoryDetail이 새로 생성될 때 Gemini로 임베딩을 생성해서 저장.
실패해도 기록 저장 자체는 막지 않음.
"""
import logging

logger = logging.getLogger(__name__)


def auto_embed_on_save(sender, instance, created, **kwargs):
    """MemoryDetail post_save 시그널 핸들러 — Celery 큐에 태스크 발행"""
    if not created:
        return

    try:
        from chat.tasks import embed_memory_task
        embed_memory_task.delay(str(instance.memory_id))
    except Exception as e:
        logger.warning('임베딩 태스크 발행 실패 (Celery 브로커 미연결?): %s', e)

    # 새 기록이 추가되면 해당 컨텍스트의 RAG 캐시 무효화
    try:
        from django.core.cache import cache
        memory = instance.memory
        if memory.group_id:
            cache.delete_pattern(f'rag:group:{memory.group_id}:q:*')
        else:
            cache.delete_pattern(f'rag:user:{memory.user_id}:q:*')
    except Exception as e:
        logger.warning('RAG 캐시 무효화 실패: %s', e)
