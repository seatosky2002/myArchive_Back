"""
chat/services.py — RAG 핵심 로직

embed_memory(memory_detail): MemoryDetail 하나를 Gemini로 임베딩해서 저장
rag_chat(user, message):     질문을 받아 유사 기록 검색 후 Gemini로 답변 생성

임베딩: google-generativeai SDK 직접 사용 (langchain-google-genai v4가 v1beta만 지원해서
        text-embedding-004가 안 되는 문제 우회)
LLM:   langchain-google-genai ChatGoogleGenerativeAI 사용
"""
import logging

import google.generativeai as genai
from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from pgvector.django import CosineDistance

from memories.models import MemoryDetail, ChatSession

logger = logging.getLogger(__name__)

# ───────────────────────────────────────────
# Gemini 클라이언트 초기화
# ───────────────────────────────────────────
genai.configure(api_key=settings.GEMINI_API_KEY)

_llm = ChatGoogleGenerativeAI(
    model='gemini-1.5-flash',
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0.7,
)

SYSTEM_PROMPT = """당신은 사용자의 개인 일기를 기반으로 대화하는 AI 비서입니다.
아래 관련 기록들을 참고해서 한국어로 친근하게 답변하세요.
기록에 없는 내용은 절대 지어내지 마세요.
기록이 충분하지 않으면 솔직하게 "해당 기록이 없어요"라고 말해주세요."""


def _get_embedding(text: str) -> list[float]:
    """google-generativeai SDK로 텍스트 임베딩 생성 (768차원)"""
    result = genai.embed_content(
        model='models/gemini-embedding-001',
        content=text,
        task_type='retrieval_document',
    )
    return result['embedding']


def embed_memory(memory_detail: MemoryDetail) -> None:
    """
    MemoryDetail 하나를 임베딩해서 content_embedding 컬럼에 저장.
    기록 저장 시그널과 bulk 임베딩 커맨드 양쪽에서 호출됨.
    """
    memory = memory_detail.memory
    # 제목 + 날짜 + 본문을 합쳐서 임베딩 (검색 품질 향상)
    text = f"{memory.title}\n{memory.visited_at}\n{memory_detail.content}"

    try:
        vector = _get_embedding(text)
        memory_detail.content_embedding = vector
        memory_detail.save(update_fields=['content_embedding'])
    except Exception as e:
        logger.error(f'임베딩 실패 (memory_id={memory.id}): {e}')
        raise


def rag_chat(user, message: str) -> dict:
    """
    RAG 챗봇 메인 함수.

    1. 질문을 임베딩
    2. pgvector로 유사 기록 상위 5개 검색
    3. 컨텍스트 구성 후 Gemini에 전달
    4. ChatSession에 저장
    5. 응답 + 출처 반환
    """
    # 1. 질문 임베딩 (검색용 task_type)
    query_vector = genai.embed_content(
        model='models/gemini-embedding-001',
        content=message,
        task_type='retrieval_query',
    )['embedding']

    # 2. 유사 기록 검색 (embedding이 있는 것만)
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

    # 4. Gemini 호출
    messages = [
        SystemMessage(content=f"{SYSTEM_PROMPT}\n\n[관련 기록]\n{context}"),
        HumanMessage(content=message),
    ]
    response = _llm.invoke(messages)
    ai_text = response.content

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
