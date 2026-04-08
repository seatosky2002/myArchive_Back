"""
chat/views.py — RAG 챗봇 API 뷰

POST /api/chat/          — 질문을 받아 RAG 응답 반환
GET  /api/chat/history/  — 대화 기록 최근 20개 반환
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from memories.models import ChatSession
from .serializers import ChatRequestSerializer, ChatResponseSerializer, ChatHistorySerializer
from . import services


class ChatRateThrottle(UserRateThrottle):
    scope = 'chat'  # settings.py DEFAULT_THROTTLE_RATES['chat'] = '30/hour'


class ChatView(APIView):
    """POST /api/chat/ — 질문 → RAG → Gemini 응답"""
    permission_classes = [IsAuthenticated]
    throttle_classes = [ChatRateThrottle]

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        message = serializer.validated_data['message']
        result = services.rag_chat(request.user, message)

        return Response(ChatResponseSerializer(result).data)


class ChatHistoryView(APIView):
    """GET /api/chat/history/ — 최근 대화 기록 20개"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = ChatSession.objects.filter(user=request.user)[:20]
        return Response(ChatHistorySerializer(sessions, many=True).data)
