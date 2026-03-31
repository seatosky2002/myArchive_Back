"""
chat/services.py — RAG 핵심 로직

임베딩 + LLM 모두 google-generativeai SDK 직접 사용.
(langchain-google-genai v4가 v1beta API만 지원해서 이 API 키로 지원되는
 모델들과 호환이 안 되는 문제를 우회)

embed_memory(memory_detail): MemoryDetail 하나를 임베딩해서 저장
rag_chat(user, message):     질문 → 유사 기록 검색 → Gemini 답변
"""
import logging
import time
import re

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from django.conf import settings
from pgvector.django import CosineDistance

from memories.models import MemoryDetail, ChatSession

logger = logging.getLogger(__name__)

# ───────────────────────────────────────────
# Gemini 클라이언트 초기화
# ───────────────────────────────────────────
genai.configure(api_key=settings.GEMINI_API_KEY)

EMBEDDING_MODEL = 'models/gemini-embedding-001'
CHAT_MODEL      = 'gemini-2.0-flash-lite'

def _retry_on_quota(fn, *args, max_retries=3, **kwargs):
    """
    429 ResourceExhausted 발생 시 retry_delay 만큼 기다렸다가 재시도.
    무료 티어 분당 한도 초과 시 자동 복구.
    """
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except ResourceExhausted as e:
            if attempt == max_retries - 1:
                raise
            # 에러 메시지에서 retry_delay(seconds) 파싱
            match = re.search(r'retry_delay\s*\{\s*seconds:\s*(\d+)', str(e))
            wait = int(match.group(1)) + 1 if match else 20
            logger.warning(f'Quota 초과, {wait}초 후 재시도 ({attempt+1}/{max_retries})')
            time.sleep(wait)


SYSTEM_PROMPT = (
    "당신은 사용자의 개인 일기를 기반으로 대화하는 AI 비서입니다.\n"
    "아래 관련 기록들을 참고해서 한국어로 친근하게 답변하세요.\n"
    "기록에 없는 내용은 절대 지어내지 마세요.\n"
    "기록이 충분하지 않으면 솔직하게 '해당 기록이 없어요'라고 말해주세요."
)


def embed_memory(memory_detail: MemoryDetail) -> None:
    """
    MemoryDetail 하나를 임베딩해서 content_embedding 컬럼에 저장.
    기록 저장 시그널과 bulk 임베딩 커맨드 양쪽에서 호출됨.
    """
    memory = memory_detail.memory
    text = f"{memory.title}\n{memory.visited_at}\n{memory_detail.content}"

    try:
        result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=text,
            task_type='retrieval_document',
        )
        memory_detail.content_embedding = result['embedding']
        memory_detail.save(update_fields=['content_embedding'])
    except Exception as e:
        logger.error(f'임베딩 실패 (memory_id={memory.id}): {e}')
        raise


def rag_chat(user, message: str) -> dict:
    """
    RAG 챗봇 메인 함수.

    1. 질문 임베딩
    2. pgvector로 유사 기록 상위 5개 검색
    3. 컨텍스트 구성 후 Gemini에 전달
    4. ChatSession에 저장
    5. 응답 + 출처 반환
    """
    # 1. 질문 임베딩
    query_result = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=message,
        task_type='retrieval_query',
    )
    query_vector = query_result['embedding']

    # 2. 유사 기록 검색
    results = (
        MemoryDetail.objects
        .filter(memory__user=user, content_embedding__isnull=False)
        .annotate(distance=CosineDistance('content_embedding', query_vector))
        .order_by('distance')
        .select_related('memory', 'memory__location', 'memory__category')[:5]
    )

    # 3. 컨텍스트 구성
    sources = []
    context_lines = []
    for md in results:
        m = md.memory
        place_name = m.location.place_name if m.location else '알 수 없는 장소'
        line = f"- [{m.visited_at}] {m.title} / 장소: {place_name} / 내용: {md.content}"
        context_lines.append(line)
        sources.append({
            'title': m.title,
            'visited_at': str(m.visited_at),
            'place_name': place_name,
            'distance': round(float(md.distance), 4),
        })

    context = '\n'.join(context_lines) if context_lines else '관련 기록이 없습니다.'

    # 4. Gemini 호출 (rate limit 시 자동 재시도)
    prompt = f"{SYSTEM_PROMPT}\n\n[관련 기록]\n{context}\n\n[질문]\n{message}"
    model = genai.GenerativeModel(CHAT_MODEL)
    response = _retry_on_quota(model.generate_content, prompt)
    ai_text = response.text

    # 5. 대화 기록 저장
    ChatSession.objects.create(
        user=user,
        query_text=message,
        ai_response=ai_text,
    )

    return {
        'response': ai_text,
        'sources': sources,
    }
