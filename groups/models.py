import uuid
import secrets
from django.conf import settings
from django.db import models


class MemberRole(models.TextChoices):
    OWNER  = 'owner',  '오너'
    ADMIN  = 'admin',  '관리자'
    MEMBER = 'member', '멤버'
    VIEWER = 'viewer', '뷰어'


class MemberStatus(models.TextChoices):
    PENDING = 'pending', '대기'
    ACTIVE  = 'active',  '활성'
    LEFT    = 'left',    '탈퇴'
    BANNED  = 'banned',  '추방'


class ActivityType(models.TextChoices):
    MEMBER_JOINED       = 'member_joined',       '멤버 가입'
    MEMBER_LEFT         = 'member_left',         '멤버 탈퇴'
    MEMBER_BANNED       = 'member_banned',        '멤버 추방'
    MEMBER_ROLE_CHANGED = 'member_role_changed',  '역할 변경'
    MEMORY_CREATED      = 'memory_created',       '기억 생성'
    MEMORY_DELETED      = 'memory_deleted',       '기억 삭제'
    GROUP_UPDATED       = 'group_updated',        '그룹 수정'
    INVITE_CODE_RESET   = 'invite_code_reset',    '초대 코드 재발급'


def _default_invite_code():
    return secrets.token_urlsafe(6)


def _default_token():
    return str(uuid.uuid4())


class Group(models.Model):
    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name          = models.CharField(max_length=100)
    description   = models.TextField(blank=True, default='')
    cover_img_url = models.TextField(null=True, blank=True)
    created_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name='created_groups',
    )
    invite_code   = models.CharField(max_length=20, unique=True, default=_default_invite_code)
    max_members   = models.PositiveIntegerField(default=20)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)
    deleted_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'groups'

    def __str__(self):
        return self.name

    @property
    def is_deleted(self):
        return self.deleted_at is not None


class GroupMember(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group      = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='members')
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='group_memberships',
    )
    role       = models.CharField(max_length=10, choices=MemberRole.choices, default=MemberRole.MEMBER)
    status     = models.CharField(max_length=10, choices=MemberStatus.choices, default=MemberStatus.PENDING)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_invitations',
    )
    joined_at  = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'group_members'
        constraints = [
            models.UniqueConstraint(fields=['group', 'user'], name='unique_group_member')
        ]
        indexes = [
            models.Index(fields=['user', 'status'], name='idx_member_user_status'),
            models.Index(fields=['group', 'status'], name='idx_member_group_status'),
        ]

    def __str__(self):
        return f'{self.user.nickname} @ {self.group.name} ({self.role})'


class GroupInvitation(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group       = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='invitations')
    invited_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='group_invitations_sent',
    )
    email       = models.EmailField(null=True, blank=True)
    token       = models.CharField(max_length=64, unique=True, default=_default_token)
    role        = models.CharField(max_length=10, choices=MemberRole.choices, default=MemberRole.MEMBER)
    expires_at  = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'group_invitations'
        indexes = [
            models.Index(fields=['expires_at'], name='idx_invitation_expires'),
            models.Index(fields=['group', 'email'], name='idx_invitation_group_email'),
        ]

    def __str__(self):
        return f'Invitation to {self.group.name} ({self.email or "link"})'


class GroupCategory(models.Model):
    group      = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='categories')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name='group_categories_created',
    )
    name       = models.CharField(max_length=50)
    color_code = models.CharField(max_length=7, default='#007AFF')

    class Meta:
        db_table = 'group_categories'
        constraints = [
            models.UniqueConstraint(fields=['group', 'name'], name='unique_group_category')
        ]

    def __str__(self):
        return f'{self.group.name} / {self.name}'


class GroupChatSession(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group       = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='chat_sessions')
    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='group_chat_sessions',
    )
    query_text  = models.TextField()
    ai_response = models.TextField()
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'group_chat_sessions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group', '-created_at'], name='idx_group_chat_recent'),
        ]

    def __str__(self):
        return f'{self.group.name} / {self.user.nickname}'


class GroupActivity(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group      = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='activities')
    actor      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='group_activities',
    )
    target     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='group_activity_targets',
    )
    type       = models.CharField(max_length=30, choices=ActivityType.choices)
    metadata   = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'group_activities'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group', '-created_at'], name='idx_activity_group_recent'),
        ]

    def __str__(self):
        return f'{self.group.name} / {self.type} by {self.actor.nickname}'
