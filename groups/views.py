import secrets
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from memories.views import MemoryPagination
from .models import Group, GroupMember, GroupActivity, MemberRole, MemberStatus, ActivityType
from .serializers import (
    GroupListSerializer, GroupDetailSerializer, GroupCreateSerializer,
    GroupUpdateSerializer, GroupMemberSerializer, GroupMemberRoleSerializer,
)


# ─── 헬퍼 ────────────────────────────────────────────────────────────────────

def _get_active_member(group, user):
    try:
        return group.members.get(user=user, status=MemberStatus.ACTIVE)
    except GroupMember.DoesNotExist:
        raise PermissionDenied('해당 그룹의 멤버가 아닙니다.')


def _require_admin(member):
    if member.role not in (MemberRole.OWNER, MemberRole.ADMIN):
        raise PermissionDenied('관리자 이상만 가능합니다.')


def _require_owner(member):
    if member.role != MemberRole.OWNER:
        raise PermissionDenied('오너만 가능합니다.')


def _log(group, actor, activity_type, target=None, metadata=None):
    GroupActivity.objects.create(
        group=group, actor=actor, target=target,
        type=activity_type, metadata=metadata,
    )


# ─── 그룹 목록 / 생성 ─────────────────────────────────────────────────────────

class GroupListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return GroupCreateSerializer
        return GroupListSerializer

    def get_queryset(self):
        return Group.objects.filter(
            members__user=self.request.user,
            members__status=MemberStatus.ACTIVE,
            deleted_at__isnull=True,
        ).distinct()

    def create(self, request, *args, **kwargs):
        serializer = GroupCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        group = serializer.save()
        out = GroupListSerializer(group, context={'request': request})
        return Response(out.data, status=status.HTTP_201_CREATED)


# ─── 그룹 상세 / 수정 / 삭제 ──────────────────────────────────────────────────

class GroupDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_group(self, pk):
        return get_object_or_404(Group, pk=pk, deleted_at__isnull=True)

    def get(self, request, pk):
        group = self._get_group(pk)
        _get_active_member(group, request.user)
        return Response(GroupDetailSerializer(group, context={'request': request}).data)

    def patch(self, request, pk):
        group  = self._get_group(pk)
        member = _get_active_member(group, request.user)
        _require_admin(member)
        serializer = GroupUpdateSerializer(group, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log(group, request.user, ActivityType.GROUP_UPDATED)
        return Response(GroupDetailSerializer(group, context={'request': request}).data)

    def delete(self, request, pk):
        group  = self._get_group(pk)
        member = _get_active_member(group, request.user)
        _require_owner(member)
        group.deleted_at = timezone.now()
        group.save(update_fields=['deleted_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─── 초대 코드로 가입 ──────────────────────────────────────────────────────────

class JoinByCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code  = request.data.get('invite_code', '').strip()
        group = get_object_or_404(Group, invite_code=code, deleted_at__isnull=True)

        existing = group.members.filter(user=request.user).first()
        if existing:
            if existing.status == MemberStatus.ACTIVE:
                raise ValidationError('이미 이 그룹의 멤버입니다.')
            if existing.status == MemberStatus.BANNED:
                raise PermissionDenied('추방된 그룹에는 재가입할 수 없습니다.')
            existing.status    = MemberStatus.ACTIVE
            existing.role      = MemberRole.MEMBER
            existing.joined_at = timezone.now()
            existing.save(update_fields=['status', 'role', 'joined_at'])
        else:
            active_count = group.members.filter(status=MemberStatus.ACTIVE).count()
            if active_count >= group.max_members:
                raise ValidationError('그룹 정원이 가득 찼습니다.')
            GroupMember.objects.create(
                group=group, user=request.user,
                role=MemberRole.MEMBER, status=MemberStatus.ACTIVE,
                joined_at=timezone.now(),
            )

        _log(group, request.user, ActivityType.MEMBER_JOINED)
        out = GroupListSerializer(group, context={'request': request})
        return Response(out.data, status=status.HTTP_200_OK)


# ─── 멤버 목록 ────────────────────────────────────────────────────────────────

class GroupMemberListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class   = GroupMemberSerializer

    def get_queryset(self):
        group = get_object_or_404(Group, pk=self.kwargs['pk'], deleted_at__isnull=True)
        _get_active_member(group, self.request.user)
        return group.members.filter(status=MemberStatus.ACTIVE).select_related('user')


# ─── 멤버 역할 변경 / 추방 ────────────────────────────────────────────────────

class GroupMemberDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _setup(self, pk):
        group  = get_object_or_404(Group, pk=pk, deleted_at__isnull=True)
        member = _get_active_member(group, self.request.user)
        return group, member

    def patch(self, request, pk, user_id):
        group, me = self._setup(pk)
        _require_admin(me)
        target = get_object_or_404(GroupMember, group=group, user_id=user_id, status=MemberStatus.ACTIVE)
        if target.role == MemberRole.OWNER:
            raise PermissionDenied('오너의 역할은 변경할 수 없습니다.')
        old_role = target.role
        serializer = GroupMemberRoleSerializer(target, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log(group, request.user, ActivityType.MEMBER_ROLE_CHANGED,
             target=target.user, metadata={'old_role': old_role, 'new_role': target.role})
        return Response(GroupMemberSerializer(target).data)

    def delete(self, request, pk, user_id):
        group, me = self._setup(pk)
        _require_admin(me)
        target = get_object_or_404(GroupMember, group=group, user_id=user_id, status=MemberStatus.ACTIVE)
        if target.role == MemberRole.OWNER:
            raise PermissionDenied('오너는 추방할 수 없습니다.')
        target.status = MemberStatus.BANNED
        target.save(update_fields=['status'])
        _log(group, request.user, ActivityType.MEMBER_BANNED, target=target.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─── 그룹 탈퇴 ───────────────────────────────────────────────────────────────

class LeaveGroupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        group  = get_object_or_404(Group, pk=pk, deleted_at__isnull=True)
        member = _get_active_member(group, request.user)
        if member.role == MemberRole.OWNER:
            raise ValidationError('오너는 탈퇴할 수 없습니다. 그룹을 삭제하거나 오너를 양도하세요.')
        member.status = MemberStatus.LEFT
        member.save(update_fields=['status'])
        _log(group, request.user, ActivityType.MEMBER_LEFT)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─── Owner 양도 ──────────────────────────────────────────────────────────────

class TransferOwnerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        group  = get_object_or_404(Group, pk=pk, deleted_at__isnull=True)
        me     = _get_active_member(group, request.user)
        _require_owner(me)

        target_user_id = request.data.get('user_id')
        if not target_user_id:
            raise ValidationError('user_id가 필요합니다.')

        target = get_object_or_404(GroupMember, group=group, user_id=target_user_id, status=MemberStatus.ACTIVE)
        if target.user == request.user:
            raise ValidationError('본인에게 양도할 수 없습니다.')

        # 현재 owner → admin, 대상 → owner
        me.role = MemberRole.ADMIN
        me.save(update_fields=['role'])
        target.role = MemberRole.OWNER
        target.save(update_fields=['role'])

        _log(group, request.user, ActivityType.MEMBER_ROLE_CHANGED,
             target=target.user,
             metadata={'old_role': 'owner', 'new_role': 'owner', 'transfer': True})

        return Response({'detail': f'{target.user.nickname}에게 그룹 오너가 양도되었습니다.'})


# ─── 초대 코드 재발급 ─────────────────────────────────────────────────────────

class ResetInviteCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        group  = get_object_or_404(Group, pk=pk, deleted_at__isnull=True)
        member = _get_active_member(group, request.user)
        _require_admin(member)
        group.invite_code = secrets.token_urlsafe(6)
        group.save(update_fields=['invite_code'])
        _log(group, request.user, ActivityType.INVITE_CODE_RESET)
        return Response({'invite_code': group.invite_code})


# ─── 그룹 활동 로그 ───────────────────────────────────────────────────────────

class GroupActivityListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        from .serializers import GroupActivitySerializer
        return GroupActivitySerializer

    def get_queryset(self):
        group  = get_object_or_404(Group, pk=self.kwargs['pk'], deleted_at__isnull=True)
        member = _get_active_member(group, self.request.user)
        _require_admin(member)
        return (
            GroupActivity.objects
            .filter(group=group)
            .select_related('actor', 'target')
            .order_by('-created_at')[:100]
        )


# ─── 그룹 카테고리 목록 / 생성 ───────────────────────────────────────────────

class GroupCategoryListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        group  = get_object_or_404(Group, pk=pk, deleted_at__isnull=True)
        _get_active_member(group, request.user)
        from .serializers import GroupCategorySerializer
        from .models import GroupCategory
        qs = GroupCategory.objects.filter(group=group)
        return Response(GroupCategorySerializer(qs, many=True).data)

    def post(self, request, pk):
        group  = get_object_or_404(Group, pk=pk, deleted_at__isnull=True)
        member = _get_active_member(group, request.user)
        _require_admin(member)
        from .serializers import GroupCategorySerializer
        from .models import GroupCategory
        serializer = GroupCategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(group=group, created_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class GroupCategoryDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_category(self, pk, category_id):
        from .models import GroupCategory
        group = get_object_or_404(Group, pk=pk, deleted_at__isnull=True)
        category = get_object_or_404(GroupCategory, pk=category_id, group=group)
        return group, category

    def patch(self, request, pk, category_id):
        group, category = self._get_category(pk, category_id)
        member = _get_active_member(group, request.user)
        _require_admin(member)
        from .serializers import GroupCategorySerializer
        serializer = GroupCategorySerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk, category_id):
        group, category = self._get_category(pk, category_id)
        member = _get_active_member(group, request.user)
        _require_admin(member)
        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─── 그룹 기억 목록 ───────────────────────────────────────────────────────────

class GroupMemoryListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class   = MemoryPagination

    def get_serializer_class(self):
        from memories.serializers import MemoryListSerializer
        return MemoryListSerializer

    def get_queryset(self):
        from memories.models import Memory
        group = get_object_or_404(Group, pk=self.kwargs['pk'], deleted_at__isnull=True)
        _get_active_member(group, self.request.user)
        return (
            Memory.objects
            .filter(group=group)
            .select_related('location', 'user')
            .prefetch_related('tags', 'images')
            .order_by('-visited_at')
        )
