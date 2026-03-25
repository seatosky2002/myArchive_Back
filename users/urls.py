from django.urls import path
from .views import LoginView, LogoutView, MeView, RegisterView

# /api/users/ 하위 URL 정의
urlpatterns = [
    path('register/', RegisterView.as_view()),  # 회원가입
    path('login/',    LoginView.as_view()),     # 로그인
    path('logout/',   LogoutView.as_view()),    # 로그아웃
    path('me/',       MeView.as_view()),        # 내 프로필 조회/수정
]
