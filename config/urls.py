from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# 루트 URL 라우터
# 각 앱의 urls.py로 요청을 위임하는 진입점
urlpatterns = [
    path('admin/',          admin.site.urls),
    path('api/users/',      include('users.urls')),      # 인증 API
    path('api/locations/',  include('locations.urls')),  # 장소 API
    path('api/memories/',   include('memories.urls')),   # 기록 API
    path('api/chat/',       include('chat.urls')),        # RAG 챗봇 API

    # Swagger / OpenAPI
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/',   SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
