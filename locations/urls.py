from django.urls import path
from .views import LocationCreateView, LocationDetailView

# /api/locations/ 하위 URL 정의
urlpatterns = [
    path('',       LocationCreateView.as_view()),    # 장소 생성 or 기존 반환
    path('<uuid:pk>/', LocationDetailView.as_view()), # 장소 상세 조회
]
