from django.urls import path
from .views import (
    MemoryDetailView,
    MemoryImageDeleteView,
    MemoryImageUploadView,
    MemoryListCreateView,
)

# /api/memories/ 하위 URL 정의
urlpatterns = [
    path('',                                        MemoryListCreateView.as_view()),    # 목록 조회 / 생성
    path('<uuid:pk>/',                              MemoryDetailView.as_view()),         # 상세 / 수정 / 삭제
    path('<uuid:pk>/images/',                       MemoryImageUploadView.as_view()),    # 이미지 업로드
    path('<uuid:pk>/images/<uuid:image_id>/',       MemoryImageDeleteView.as_view()),    # 이미지 삭제
]
