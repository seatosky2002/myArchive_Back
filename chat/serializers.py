"""
chat/serializers.py — 챗봇 요청/응답 직렬화
"""
from rest_framework import serializers
from memories.models import ChatSession


class ChatRequestSerializer(serializers.Serializer):
    """POST /api/chat/ 요청 본문"""
    message = serializers.CharField(max_length=1000)


class SourceSerializer(serializers.Serializer):
    """RAG 검색 출처 하나"""
    title     = serializers.CharField()
    visited_at = serializers.CharField()
    place_name = serializers.CharField()
    distance  = serializers.FloatField()


class ChatResponseSerializer(serializers.Serializer):
    """POST /api/chat/ 응답"""
    response = serializers.CharField()
    sources  = SourceSerializer(many=True)


class ChatHistorySerializer(serializers.ModelSerializer):
    """GET /api/chat/history/ 응답"""
    class Meta:
        model = ChatSession
        fields = ('id', 'query_text', 'ai_response', 'created_at')
