from django.utils import timezone
from rest_framework import serializers
from .models import Group, GroupMember, GroupCategory, MemberRole, MemberStatus


class GroupMemberUserSerializer(serializers.Serializer):
    id       = serializers.UUIDField()
    nickname = serializers.CharField()
    email    = serializers.EmailField()


class GroupMemberSerializer(serializers.ModelSerializer):
    user = GroupMemberUserSerializer(read_only=True)

    class Meta:
        model  = GroupMember
        fields = ['id', 'user', 'role', 'status', 'joined_at']


class GroupListSerializer(serializers.ModelSerializer):
    """그룹 목록용 — my_role 포함"""
    my_role      = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()

    class Meta:
        model  = Group
        fields = ['id', 'name', 'description', 'cover_img_url',
                  'invite_code', 'max_members', 'my_role', 'member_count', 'created_at']

    def get_my_role(self, obj):
        user = self.context['request'].user
        try:
            m = obj.members.get(user=user, status='active')
            return m.role
        except GroupMember.DoesNotExist:
            return None

    def get_member_count(self, obj):
        return obj.members.filter(status='active').count()


class GroupDetailSerializer(GroupListSerializer):
    class Meta(GroupListSerializer.Meta):
        fields = GroupListSerializer.Meta.fields + ['updated_at']


class GroupCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Group
        fields = ['name', 'description', 'cover_img_url', 'max_members']

    def create(self, validated_data):
        user  = self.context['request'].user
        group = Group.objects.create(created_by=user, **validated_data)
        # 생성자를 owner 멤버로 즉시 등록
        GroupMember.objects.create(
            group=group,
            user=user,
            role=MemberRole.OWNER,
            status=MemberStatus.ACTIVE,
            joined_at=timezone.now(),
        )
        return group


class GroupUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Group
        fields = ['name', 'description', 'cover_img_url', 'max_members']


class GroupMemberRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = GroupMember
        fields = ['role']

    def validate_role(self, value):
        if value == 'owner':
            raise serializers.ValidationError('owner 역할은 직접 부여할 수 없습니다.')
        return value


class GroupCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = GroupCategory
        fields = ['id', 'name', 'color_code']


class InviteCodeSerializer(serializers.Serializer):
    invite_code = serializers.CharField()
