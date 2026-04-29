from rest_framework import serializers
from locations.serializers import LocationSerializer
from .models import Category, Memory, MemoryDetail, MemoryImage, Tag


class TagSerializer(serializers.ModelSerializer):
    """태그 읽기용. Memory 응답에 tags 배열로 중첩."""
    class Meta:
        model = Tag
        fields = ('id', 'name')


class MemoryImageSerializer(serializers.ModelSerializer):
    """이미지 읽기용. Memory 상세 응답에 images 배열로 중첩."""
    url = serializers.SerializerMethodField()

    def get_url(self, obj):
        if obj.image:
            return obj.image.url
        return None

    class Meta:
        model = MemoryImage
        fields = ('id', 'url', 'created_at')


class CategorySerializer(serializers.ModelSerializer):
    """
    카테고리 읽기/쓰기용.
    GET /api/memories/categories/ 및 Memory 응답에 중첩 사용.
    """
    class Meta:
        model = Category
        fields = ('id', 'name', 'color_code')

    def create(self, validated_data):
        # 카테고리는 반드시 로그인한 유저 소유로 생성
        user = self.context['request'].user
        return Category.objects.create(user=user, **validated_data)


class MemoryListSerializer(serializers.ModelSerializer):
    """
    기록 목록/마커용 경량 Serializer.
    GET /api/memories/ 응답에 사용.
    content(본문)는 포함하지 않아 MemoryDetail JOIN 없이 빠르게 조회.
    tags는 이름만 문자열 배열로 반환.
    """
    location = LocationSerializer(read_only=True)
    tags = serializers.SerializerMethodField()
    mood_display = serializers.CharField(source='get_mood_display', read_only=True)
    weather_display = serializers.CharField(source='get_weather_display', read_only=True)

    class Meta:
        model = Memory
        fields = (
            'id', 'title', 'mood', 'mood_display', 'weather', 'weather_display',
            'visited_at', 'created_at', 'location', 'category', 'tags',
        )

    def get_tags(self, obj):
        # 태그 이름만 문자열 리스트로 반환 (프론트 칩 UI용)
        return list(obj.tags.values_list('name', flat=True))


class MemoryDetailSerializer(serializers.ModelSerializer):
    """
    기록 상세 Serializer.
    GET /api/memories/<id>/ 응답에 사용.
    MemoryDetail(content)을 select_related로 함께 조회하여 본문 포함.
    """
    location = LocationSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    images = MemoryImageSerializer(many=True, read_only=True)
    category = CategorySerializer(read_only=True)
    content = serializers.CharField(source='detail.content', read_only=True)
    mood_display = serializers.CharField(source='get_mood_display', read_only=True)
    weather_display = serializers.CharField(source='get_weather_display', read_only=True)

    class Meta:
        model = Memory
        fields = (
            'id', 'title', 'mood', 'mood_display', 'weather', 'weather_display',
            'visited_at', 'created_at', 'updated_at',
            'location', 'category', 'tags', 'images', 'content',
        )


class MemoryCreateSerializer(serializers.Serializer):
    """
    기록 생성/수정 쓰기용 Serializer.
    POST /api/memories/ 및 PUT /api/memories/<id>/ 에 사용.

    요청 구조:
    {
      "title": "경복궁 산책",
      "mood": "peaceful",
      "weather": "sunny",
      "visited_at": "2026-03-25",
      "location_id": "<uuid>",        # 이미 생성된 Location ID
      "category_id": 1,               # nullable
      "content": "오늘은 날씨가...",
      "tags": ["산책", "봄", "서울"]   # 문자열 배열
    }
    """
    title       = serializers.CharField(max_length=200)
    mood        = serializers.ChoiceField(choices=Memory.mood.field.choices)
    weather     = serializers.ChoiceField(choices=Memory.weather.field.choices)
    visited_at  = serializers.DateField()
    location_id = serializers.UUIDField()
    category_id = serializers.IntegerField(required=False, allow_null=True)
    content     = serializers.CharField()
    tags        = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        default=list,
    )

    def validate_location_id(self, value):
        """location_id가 실제로 존재하는 Location인지 검증"""
        from locations.models import Location
        if not Location.objects.filter(pk=value).exists():
            raise serializers.ValidationError('존재하지 않는 장소입니다.')
        return value

    def validate_category_id(self, value):
        """category_id가 있으면 요청 유저 소유 카테고리인지 검증"""
        if value is None:
            return value
        user = self.context['request'].user
        if not Category.objects.filter(pk=value, user=user).exists():
            raise serializers.ValidationError('존재하지 않는 카테고리입니다.')
        return value

    def create(self, validated_data):
        """
        1. Memory 생성
        2. MemoryDetail(content) 생성
        3. Tag bulk_create
        """
        from locations.models import Location
        tags_data = validated_data.pop('tags', [])
        content = validated_data.pop('content')
        user = self.context['request'].user

        memory = Memory.objects.create(
            user=user,
            location_id=validated_data.pop('location_id'),
            category_id=validated_data.pop('category_id', None),
            **validated_data,
        )
        MemoryDetail.objects.create(memory=memory, content=content)

        # 태그 bulk_create (ignore_conflicts로 unique 위반 무시)
        Tag.objects.bulk_create(
            [Tag(memory=memory, name=name) for name in tags_data],
            ignore_conflicts=True,
        )
        return memory

    def update(self, instance, validated_data):
        """
        1. Memory 필드 업데이트
        2. MemoryDetail content 업데이트
        3. 기존 태그 전체 삭제 후 새로 bulk_create
        """
        tags_data = validated_data.pop('tags', [])
        content = validated_data.pop('content', None)

        # Memory 필드 업데이트
        for attr, value in validated_data.items():
            if attr == 'location_id':
                instance.location_id = value
            elif attr == 'category_id':
                instance.category_id = value
            else:
                setattr(instance, attr, value)
        instance.save()

        # MemoryDetail 업데이트
        if content is not None:
            detail, _ = MemoryDetail.objects.get_or_create(memory=instance)
            detail.content = content
            detail.save()

        # 태그 교체 (기존 삭제 → 새로 생성)
        instance.tags.all().delete()
        Tag.objects.bulk_create(
            [Tag(memory=instance, name=name) for name in tags_data],
            ignore_conflicts=True,
        )
        return instance
