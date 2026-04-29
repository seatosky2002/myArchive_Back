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

from .models import Category, Memory, MemoryImage
from .serializers import (
    CategorySerializer,
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
        # 본인 기록만 조회, 위치/카테고리 select_related로 N+1 방지
        queryset = (
            Memory.objects
            .filter(user=request.user)
            .select_related('location__address_detail', 'category')
            .prefetch_related('tags')
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

    def get_object(self, pk, user):
        """본인 기록만 조회, 없으면 None 반환"""
        try:
            return (
                Memory.objects
                .select_related('location__address_detail__region', 'category', 'detail')
                .prefetch_related('tags', 'images')
                .get(pk=pk, user=user)
            )
        except Memory.DoesNotExist:
            return None

    def get(self, request, pk):
        memory = self.get_object(pk, request.user)
        if not memory:
            return Response({'detail': '기록을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(MemoryDetailSerializer(memory).data)

    def put(self, request, pk):
        memory = self.get_object(pk, request.user)
        if not memory:
            return Response({'detail': '기록을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = MemoryCreateSerializer(
            memory,
            data=request.data,
            context={'request': request},
            partial=True,   # 일부 필드만 수정 허용
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(MemoryDetailSerializer(updated).data)

    def delete(self, request, pk):
        memory = self.get_object(pk, request.user)
        if not memory:
            return Response({'detail': '기록을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        memory.delete()  # CASCADE로 MemoryDetail, Tag, Image 자동 삭제
        return Response(status=status.HTTP_204_NO_CONTENT)


class CategoryListCreateView(APIView):
    """
    GET  /api/memories/categories/ → 내 카테고리 목록
    POST /api/memories/categories/ → 카테고리 생성
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        categories = Category.objects.filter(user=request.user)
        return Response(CategorySerializer(categories, many=True).data)

    def post(self, request):
        serializer = CategorySerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CategoryDetailView(APIView):
    """
    PUT    /api/memories/categories/<id>/ → 카테고리 수정
    DELETE /api/memories/categories/<id>/ → 카테고리 삭제
    본인 카테고리가 아니면 404 반환.
    """
    permission_classes = (IsAuthenticated,)

    def get_object(self, pk, user):
        try:
            return Category.objects.get(pk=pk, user=user)
        except Category.DoesNotExist:
            return None

    def put(self, request, pk):
        category = self.get_object(pk, request.user)
        if not category:
            return Response({'detail': '카테고리를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CategorySerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        category = self.get_object(pk, request.user)
        if not category:
            return Response({'detail': '카테고리를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        category.delete()  # memories의 category_id는 SET_NULL로 처리됨
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
