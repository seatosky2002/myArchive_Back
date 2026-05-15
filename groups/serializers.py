from django.utils import timezone
from rest_framework import serializers
from .models import Group, GroupMember, GroupCategory, GroupActivity, MemberRole, MemberStatus


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

    def validate_name(self, value):
        group = self.context.get('group') or (self.instance.group if self.instance else None)
        if group:
            qs = GroupCategory.objects.filter(group=group, name=value)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError('이미 존재하는 카테고리 이름입니다.')
        return value

    def create(self, validated_data):
        return GroupCategory.objects.create(**validated_data)


class GroupActivitySerializer(serializers.ModelSerializer):
    actor_nickname  = serializers.CharField(source='actor.nickname', read_only=True)
    target_nickname = serializers.CharField(source='target.nickname', read_only=True, default=None)

    class Meta:
        model  = GroupActivity
        fields = ['id', 'type', 'actor_nickname', 'target_nickname', 'metadata', 'created_at']


class InviteCodeSerializer(serializers.Serializer):
    invite_code = serializers.CharField()
