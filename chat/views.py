"""
chat/views.py — RAG 챗봇 API 뷰

POST /api/chat/              — 질문을 받아 RAG 응답 반환
GET  /api/chat/history/      — 대화 기록 최근 20개 반환
GET  /api/chat/suggestions/  — 그룹 내 다른 멤버가 최근 물어본 질문 최대 5개 반환
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from memories.models import ChatSession
from groups.models import GroupChatSession, Group, GroupMember, MemberStatus
from .serializers import ChatRequestSerializer, ChatResponseSerializer, ChatHistorySerializer, GroupChatHistorySerializer
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

        message  = serializer.validated_data['message']
        group_id = serializer.validated_data.get('group_id')
        group    = None

        if group_id:
            try:
                group = Group.objects.get(pk=group_id, deleted_at__isnull=True)
            except Group.DoesNotExist:
                return Response({'detail': '존재하지 않는 그룹입니다.'}, status=status.HTTP_400_BAD_REQUEST)
            if not group.members.filter(user=request.user, status=MemberStatus.ACTIVE).exists():
                return Response({'detail': '해당 그룹의 멤버가 아닙니다.'}, status=status.HTTP_403_FORBIDDEN)

        result = services.rag_chat(request.user, message, group=group)
        return Response(ChatResponseSerializer(result).data)


class ChatHistoryView(APIView):
    """GET /api/chat/history/?group_id=<uuid> — 대화 기록 최근 20개"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        group_id = request.query_params.get('group_id')
        if group_id:
            try:
                group = Group.objects.get(pk=group_id, deleted_at__isnull=True)
            except Group.DoesNotExist:
                return Response({'detail': '존재하지 않는 그룹입니다.'}, status=status.HTTP_400_BAD_REQUEST)
            if not group.members.filter(user=request.user, status=MemberStatus.ACTIVE).exists():
                return Response({'detail': '해당 그룹의 멤버가 아닙니다.'}, status=status.HTTP_403_FORBIDDEN)
            sessions = GroupChatSession.objects.filter(group=group)[:20]
            return Response(GroupChatHistorySerializer(sessions, many=True).data)

        sessions = ChatSession.objects.filter(user=request.user)[:20]
        return Response(ChatHistorySerializer(sessions, many=True).data)


class GroupChatSuggestionsView(APIView):
    """GET /api/chat/suggestions/?group_id=<uuid> — 다른 멤버가 최근 물어본 질문 최대 5개"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        group_id = request.query_params.get('group_id')
        if not group_id:
            return Response({'questions': []})

        try:
            group = Group.objects.get(pk=group_id, deleted_at__isnull=True)
        except Group.DoesNotExist:
            return Response({'detail': '존재하지 않는 그룹입니다.'}, status=status.HTTP_400_BAD_REQUEST)

        if not group.members.filter(user=request.user, status=MemberStatus.ACTIVE).exists():
            return Response({'detail': '해당 그룹의 멤버가 아닙니다.'}, status=status.HTTP_403_FORBIDDEN)

        recent_queries = (
            GroupChatSession.objects
            .filter(group=group)
            .exclude(user=request.user)
            .order_by('-created_at')
            .values_list('query_text', flat=True)[:50]
        )

        seen = set()
        unique_questions = []
        for q in recent_queries:
            if q not in seen:
                seen.add(q)
                unique_questions.append(q)
                if len(unique_questions) == 5:
                    break

        return Response({'questions': unique_questions})
