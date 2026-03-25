from django.urls import path
from .views import (
    CategoryDetailView,
    CategoryListCreateView,
    MemoryDetailView,
    MemoryListCreateView,
)

# /api/memories/ 하위 URL 정의
urlpatterns = [
    path('',                        MemoryListCreateView.as_view()),    # 목록 조회 / 생성
    path('<uuid:pk>/',              MemoryDetailView.as_view()),         # 상세 / 수정 / 삭제
    path('categories/',             CategoryListCreateView.as_view()),   # 카테고리 목록 / 생성
    path('categories/<int:pk>/',    CategoryDetailView.as_view()),       # 카테고리 수정 / 삭제
]
