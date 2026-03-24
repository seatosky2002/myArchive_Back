import uuid
from django.conf import settings
from django.db import models

try:
    from pgvector.django import VectorField
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False


class MoodType(models.TextChoices):
    PEACEFUL  = 'peaceful',  '평화로운'
    HAPPY     = 'happy',     '행복한'
    CALM      = 'calm',      '차분한'
    ENERGETIC = 'energetic', '활기찬'
    SAD       = 'sad',       '슬픈'
    EXCITED   = 'excited',   '신나는'


class WeatherType(models.TextChoices):
    SUNNY   = 'sunny',   '맑음'
    CLOUDY  = 'cloudy',  '흐림'
    RAINY   = 'rainy',   '비'
    SNOWY   = 'snowy',   '눈'
    NIGHT   = 'night',   '밤'
    SUNRISE = 'sunrise', '새벽'


class Category(models.Model):
    """사용자 정의 카테고리"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='categories',
    )
    name = models.CharField(max_length=50)
    color_code = models.CharField(max_length=7, default='#007AFF', help_text='Hex color (ex: #007AFF)')

    class Meta:
        db_table = 'categories'

    def __str__(self):
        return f'{self.user.nickname} - {self.name}'


class Memory(models.Model):
    """기록 메타데이터 (경량 — 목록/지도 마커용)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='memories',
    )
    location = models.ForeignKey(
        'locations.Location',
        on_delete=models.PROTECT,
        related_name='memories',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='memories',
    )
    title = models.CharField(max_length=200)
    mood = models.CharField(max_length=20, choices=MoodType.choices)
    weather = models.CharField(max_length=20, choices=WeatherType.choices)
    visited_at = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'memories'
        ordering = ['-visited_at']

    def __str__(self):
        return f'[{self.visited_at}] {self.title}'


class MemoryDetail(models.Model):
    """기록 본문 + AI 벡터 (중량 — 수직 파티셔닝)"""
    memory = models.OneToOneField(
        Memory,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='detail',
    )
    content = models.TextField()

    if PGVECTOR_AVAILABLE:
        content_embedding = VectorField(dimensions=1536, null=True, blank=True)
    else:
        # pgvector 미설치 시 JSONField로 대체
        # TODO: pgvector 설치 후 VectorField(dimensions=1536)으로 교체
        content_embedding = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'memory_details'

    def __str__(self):
        return f'Detail of {self.memory.title}'


class Tag(models.Model):
    """기록 태그"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    memory = models.ForeignKey(
        Memory,
        on_delete=models.CASCADE,
        related_name='tags',
    )
    name = models.CharField(max_length=50)

    class Meta:
        db_table = 'tags'
        constraints = [
            models.UniqueConstraint(fields=['memory', 'name'], name='unique_memory_tag')
        ]

    def __str__(self):
        return self.name


class MemoryImage(models.Model):
    """기록 첨부 이미지"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    memory = models.ForeignKey(
        Memory,
        on_delete=models.CASCADE,
        related_name='images',
    )
    storage_url = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'memory_images'

    def __str__(self):
        return f'Image of {self.memory.title}'


class ChatSession(models.Model):
    """AI 채팅 기록"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_sessions',
    )
    query_text = models.TextField()
    ai_response = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'chat_sessions'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.nickname} - {self.created_at:%Y-%m-%d %H:%M}'
