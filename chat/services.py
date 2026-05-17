"""
chat/services.py — RAG 핵심 로직

google.genai 새 SDK 사용 (google.generativeai deprecated).

embed_memory(memory_detail):              MemoryDetail 하나를 임베딩해서 저장
rag_chat(user, message):                  질문 → 유사 기록 검색 → Gemini 답변
selective_cache_invalidation(memory_detail): 새 기억과 유사한 캐시 질문만 삭제
"""
import hashlib
import logging
import time
import re

import numpy as np
from google import genai
from google.genai import types
from google.api_core.exceptions import ResourceExhausted
from django.conf import settings
from django.core.cache import cache
from pgvector.django import CosineDistance

from memories.models import MemoryDetail, ChatSession
from groups.models import GroupChatSession

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=settings.GEMINI_API_KEY)

EMBEDDING_MODEL = 'gemini-embedding-001'
CHAT_MODEL      = 'gemini-2.5-flash'

RAG_CACHE_TTL         = 7 * 24 * 3600  # 7일
SEMANTIC_HIT_THRESHOLD   = 0.92        # 캐시 히트 유사도 임계값
INVALIDATION_THRESHOLD   = 0.85        # 캐시 무효화 유사도 임계값
MAX_INDEX_SIZE           = 100         # 유저당 최대 캐시 인덱스 크기

CACHE_KEY_TPL = 'rag:{context_id}:q:{hash}'
INDEX_KEY_TPL = 'rag:{context_id}:idx'

SYSTEM_PROMPT = (
    "당신은 사용자의 개인 일기를 기반으로 대화하는 AI 비서입니다.\n"
    "아래 관련 기록들을 참고해서 한국어로 친근하게 답변하세요.\n"
    "기록에 없는 내용은 절대 지어내지 마세요.\n"
    "기록이 충분하지 않으면 솔직하게 '해당 기록이 없어요'라고 말해주세요."
)


def _retry_on_quota(fn, *args, max_retries=3, **kwargs):
    """429 ResourceExhausted 시 retry_delay 만큼 기다렸다가 재시도"""
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except ResourceExhausted as e:
            if attempt == max_retries - 1:
                raise
            match = re.search(r'retry_delay\s*\{\s*seconds:\s*(\d+)', str(e))
            wait = int(match.group(1)) + 1 if match else 20
            logger.warning(f'Quota 초과, {wait}초 후 재시도 ({attempt+1}/{max_retries})')
            time.sleep(wait)


def _cosine_sim(a, b) -> float:
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 0 else 0.0


def _get_index(context_id: str) -> list:
    return cache.get(INDEX_KEY_TPL.format(context_id=context_id)) or []


def _save_index(context_id: str, index: list):
    cache.set(INDEX_KEY_TPL.format(context_id=context_id), index, timeout=RAG_CACHE_TTL)


def _add_to_index(context_id: str, msg_hash: str, question_text: str):
    index = _get_index(context_id)
    if any(e['hash'] == msg_hash for e in index):
        return
    index.append({'hash': msg_hash, 'question': question_text})
    if len(index) > MAX_INDEX_SIZE:
        index = index[-MAX_INDEX_SIZE:]
    _save_index(context_id, index)


def _semantic_cache_lookup(context_id: str, query_embedding: list):
    """
    캐시 인덱스에서 유사한 질문을 검색.
    SEMANTIC_HIT_THRESHOLD 이상이면 캐시 결과 반환, 아니면 None.
    """
    index = _get_index(context_id)
    if not index:
        return None

    best_sim, best_result = 0.0, None
    for entry in index:
        key = CACHE_KEY_TPL.format(context_id=context_id, hash=entry['hash'])
        cached = cache.get(key)
        if not cached or 'question_embedding' not in cached:
            continue
        sim = _cosine_sim(query_embedding, cached['question_embedding'])
        if sim > best_sim:
            best_sim, best_result = sim, cached

    if best_sim >= SEMANTIC_HIT_THRESHOLD:
        logger.info(f'시맨틱 캐시 히트: context={context_id}, sim={best_sim:.3f}')
        return {'response': best_result['response'], 'sources': best_result['sources']}
    return None


def embed_memory(memory_detail: MemoryDetail) -> None:
    """
    MemoryDetail 하나를 임베딩해서 content_embedding 컬럼에 저장.
    기록 저장 시그널과 bulk 임베딩 커맨드 양쪽에서 호출됨.
    """
    memory = memory_detail.memory
    text = f"{memory.title}\n{memory.visited_at}\n{memory_detail.content}"

    try:
        result = _client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(task_type='RETRIEVAL_DOCUMENT'),
        )
        memory_detail.content_embedding = result.embeddings[0].values
        memory_detail.save(update_fields=['content_embedding'])
    except Exception as e:
        logger.error(f'임베딩 실패 (memory_id={memory.id}): {e}')
        raise


def selective_cache_invalidation(memory_detail: MemoryDetail) -> None:
    """
    새 기억의 임베딩과 유사도가 높은 캐시 질문만 선택적으로 삭제.
    INVALIDATION_THRESHOLD(0.85) 이상인 캐시만 제거.
    임베딩 완료 후 Celery 태스크에서 호출됨.
    """
    if not memory_detail.content_embedding:
        return

    memory = memory_detail.memory
    context_id = f'group:{memory.group_id}' if memory.group_id else f'user:{memory.user_id}'
    memory_embedding = list(memory_detail.content_embedding)

    index = _get_index(context_id)
    if not index:
        return

    new_index = []
    invalidated = 0
    for entry in index:
        key = CACHE_KEY_TPL.format(context_id=context_id, hash=entry['hash'])
        cached = cache.get(key)
        if not cached or 'question_embedding' not in cached:
            continue
        sim = _cosine_sim(memory_embedding, cached['question_embedding'])
        if sim >= INVALIDATION_THRESHOLD:
            cache.delete(key)
            invalidated += 1
            logger.info(f'캐시 무효화: q="{entry["question"][:40]}", sim={sim:.3f}')
        else:
            new_index.append(entry)

    if invalidated:
        _save_index(context_id, new_index)
        logger.info(f'선택적 무효화 완료: context={context_id}, {invalidated}개 삭제, {len(new_index)}개 유지')


def rag_chat(user, message: str, group=None) -> dict:
    """
    RAG 챗봇 메인 함수.

    group=None  → 개인 기록에서 검색, ChatSession 저장
    group=Group → 해당 그룹 기록에서 검색, GroupChatSession 저장
    """
    context_id = f'group:{group.id}' if group else f'user:{user.id}'
    msg_hash   = hashlib.sha256(message.strip().lower().encode()).hexdigest()[:16]
    cache_key  = CACHE_KEY_TPL.format(context_id=context_id, hash=msg_hash)

    # 1. 완전 일치 캐시 (임베딩 API 호출 없이 즉시 반환)
    exact = cache.get(cache_key)
    if exact:
        logger.info(f'정확 캐시 히트: context={context_id}')
        result = {'response': exact['response'], 'sources': exact['sources']}
    else:
        # 2. 질문 임베딩
        query_result = _retry_on_quota(
            _client.models.embed_content,
            model=EMBEDDING_MODEL,
            contents=message,
            config=types.EmbedContentConfig(task_type='RETRIEVAL_QUERY'),
        )
        query_vector = query_result.embeddings[0].values

        # 3. 의미 유사도 캐시 검색
        semantic_hit = _semantic_cache_lookup(context_id, query_vector)
        if semantic_hit:
            result = semantic_hit
        else:
            # 4. pgvector 유사 기록 검색
            if group:
                base_qs = MemoryDetail.objects.filter(
                    memory__group=group,
                    content_embedding__isnull=False,
                )
            else:
                base_qs = MemoryDetail.objects.filter(
                    memory__user=user,
                    memory__group__isnull=True,
                    content_embedding__isnull=False,
                )

            results = (
                base_qs
                .annotate(distance=CosineDistance('content_embedding', query_vector))
                .order_by('distance')
                .select_related('memory', 'memory__location', 'memory__user')[:5]
            )

            DISTANCE_THRESHOLD = 0.5
            sources = []
            context_lines = []
            for md in results:
                if md.distance > DISTANCE_THRESHOLD:
                    continue
                m = md.memory
                place_name = m.location.place_name if m.location else '알 수 없는 장소'
                author = m.author_nickname or m.user.nickname
                content_preview = md.content[:500]
                line = f"- [{m.visited_at}] {m.title} (작성자: {author}) / 장소: {place_name} / 내용: {content_preview}"
                context_lines.append(line)
                sources.append({
                    'title': m.title,
                    'visited_at': str(m.visited_at),
                    'place_name': place_name,
                    'distance': round(float(md.distance), 4),
                })

            context = '\n'.join(context_lines) if context_lines else '관련 기록이 없습니다.'

            # 5. Gemini 생성
            prompt = f"{SYSTEM_PROMPT}\n\n[관련 기록]\n{context}\n\n[질문]\n{message}"
            response = _retry_on_quota(
                _client.models.generate_content,
                model=CHAT_MODEL,
                contents=prompt,
            )
            result = {'response': response.text, 'sources': sources}

            # 6. 캐시 저장 (question_embedding 함께 저장)
            cache_data = {**result, 'question_embedding': list(query_vector), 'question_text': message}
            cache.set(cache_key, cache_data, timeout=RAG_CACHE_TTL)
            _add_to_index(context_id, msg_hash, message)

    # 7. 대화 기록 저장
    if group:
        GroupChatSession.objects.create(
            group=group,
            user=user,
            query_text=message,
            ai_response=result['response'],
        )
    else:
        ChatSession.objects.create(
            user=user,
            query_text=message,
            ai_response=result['response'],
        )

    return result
