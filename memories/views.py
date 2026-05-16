from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class MemoryPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200

from .models import Memory, MemoryImage
from .serializers import (
    MemoryCreateSerializer,
    MemoryDetailSerializer,
    MemoryImageSerializer,
    MemoryListSerializer,
)


class MemoryListCreateView(APIView):
    """
    GET  /api/memories/
        - 로그인 유저의 기록 목록 반환 (경량 — content 제외).
        - MemoryDetail JOIN 없이 Memory만 조회하여 성능 최적화 (수직 파티셔닝 효과).
        - ?search=키워드 : 제목 또는 태그명 필터링.

    POST /api/memories/
        - Memory + MemoryDetail(content) + Tag 동시 생성.
        - location_id는 이미 생성된 Location UUID 전달.
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        # 개인 기억만 조회 (group=null). 그룹 기억은 /api/groups/{id}/memories/ 에서 조회
        queryset = (
            Memory.objects
            .filter(user=request.user, group__isnull=True)
            .select_related('location__address_detail')
            .prefetch_related('tags', 'images')
            .order_by('-visited_at')
        )

        # 제목 또는 태그로 검색
        search = request.query_params.get('search', '').strip()[:100]
        if len(search) >= 1:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(tags__name__icontains=search)
            ).distinct()

        paginator = MemoryPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = MemoryListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = MemoryCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        memory = serializer.save()

        # 생성 후 상세 Serializer로 응답 (content 포함)
        return Response(
            MemoryDetailSerializer(memory).data,
            status=status.HTTP_201_CREATED,
        )


class MemoryDetailView(APIView):
    """
    GET    /api/memories/<id>/ → 기록 상세 (content, tags, images 포함)
    PUT    /api/memories/<id>/ → 기록 수정
    DELETE /api/memories/<id>/ → 기록 삭제 (CASCADE: detail, tags, images 자동 삭제)
    본인 기록이 아니면 404 반환 (존재 여부 노출 방지).
    """
    permission_classes = (IsAuthenticated,)

    def _get_memory(self, pk):
        try:
            return (
                Memory.objects
                .select_related('location__address_detail__region', 'detail', 'group')
                .prefetch_related('tags', 'images')
                .get(pk=pk)
            )
        except Memory.DoesNotExist:
            return None

    def _check_read_permission(self, memory, user):
        """본인 기억이거나 그룹 활성 멤버면 열람 허용"""
        if memory.user == user:
            return True
        if memory.group:
            from groups.models import GroupMember, MemberStatus
            return memory.group.members.filter(user=user, status=MemberStatus.ACTIVE).exists()
        return False

    def _check_write_permission(self, memory, user):
        """수정은 본인만"""
        return memory.user == user

    def _check_delete_permission(self, memory, user):
        """삭제는 본인 or 그룹 admin/owner"""
        if memory.user == user:
            return True
        if memory.group:
            from groups.models import GroupMember, MemberStatus, MemberRole
            try:
                m = memory.group.members.get(user=user, status=MemberStatus.ACTIVE)
                return m.role in (MemberRole.OWNER, MemberRole.ADMIN)
            except GroupMember.DoesNotExist:
                pass
        return False

    def get(self, request, pk):
        memory = self._get_memory(pk)
        if not memory or not self._check_read_permission(memory, request.user):
            return Response({'detail': '기록을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(MemoryDetailSerializer(memory).data)

    def put(self, request, pk):
        memory = self._get_memory(pk)
        if not memory or not self._check_write_permission(memory, request.user):
            return Response({'detail': '기록을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = MemoryCreateSerializer(
            memory,
            data=request.data,
            context={'request': request},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(MemoryDetailSerializer(updated).data)

    def delete(self, request, pk):
        memory = self._get_memory(pk)
        if not memory or not self._check_delete_permission(memory, request.user):
            return Response({'detail': '기록을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        # 그룹 admin이 타인 기억 삭제 시 활동 로그 기록
        if memory.group and memory.user != request.user:
            from groups.models import GroupActivity, ActivityType
            GroupActivity.objects.create(
                group=memory.group,
                actor=request.user,
                type=ActivityType.MEMORY_DELETED,
                metadata={'memory_id': str(memory.id), 'memory_title': memory.title},
            )

        memory.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _normalize_to_jpeg(upload_file):
    """
    HEIC/HEIF 등 브라우저 미지원 포맷을 JPEG로 변환.
    JPEG/PNG/WebP 등 일반 포맷은 그대로 반환.
    반환값: (InMemoryUploadedFile, filename)
    """
    import io
    from django.core.files.uploadedfile import InMemoryUploadedFile

    name = upload_file.name or ''
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''

    if ext in ('heic', 'heif'):
        from pillow_heif import register_heif_opener
        from PIL import Image
        register_heif_opener()
        img = Image.open(upload_file)
        img = img.convert('RGB')
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=88)
        buf.seek(0)
        new_name = name.rsplit('.', 1)[0] + '.jpg'
        return InMemoryUploadedFile(buf, 'image', new_name, 'image/jpeg', buf.getbuffer().nbytes, None)

    return upload_file


class MemoryImageUploadView(APIView):
    """
    POST /api/memories/<id>/images/
        - multipart/form-data로 이미지 파일 업로드
        - HEIC/HEIF는 서버에서 JPEG로 자동 변환
        - 업로드된 이미지 정보(id, url) 반환
    """
    permission_classes = (IsAuthenticated,)
    parser_classes = (MultiPartParser,)

    def post(self, request, pk):
        try:
            memory = Memory.objects.get(pk=pk, user=request.user)
        except Memory.DoesNotExist:
            return Response({'detail': '기록을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        image_file = request.FILES.get('image')
        if not image_file:
            return Response({'detail': '이미지 파일이 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        image_file = _normalize_to_jpeg(image_file)
        img = MemoryImage.objects.create(memory=memory, image=image_file)
        return Response(MemoryImageSerializer(img).data, status=status.HTTP_201_CREATED)


class MemoryImageDeleteView(APIView):
    """
    DELETE /api/memories/<id>/images/<image_id>/
        - 이미지 삭제 (파일 + DB 레코드)
    """
    permission_classes = (IsAuthenticated,)

    def delete(self, request, pk, image_id):
        try:
            img = MemoryImage.objects.get(pk=image_id, memory__pk=pk, memory__user=request.user)
        except MemoryImage.DoesNotExist:
            return Response({'detail': '이미지를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        img.image.delete(save=False)  # 파일도 함께 삭제
        img.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
