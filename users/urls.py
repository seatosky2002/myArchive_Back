from django.urls import path
from .views import CookieTokenRefreshView, LoginView, LogoutView, MeView, RegisterView

# /api/users/ 하위 URL 정의
urlpatterns = [
    path('register/',      RegisterView.as_view()),          # 회원가입
    path('login/',         LoginView.as_view()),             # 로그인
    path('logout/',        LogoutView.as_view()),            # 로그아웃
    path('token/refresh/', CookieTokenRefreshView.as_view()),  # access 갱신 (쿠키 기반)
    path('me/',            MeView.as_view()),                # 내 프로필 조회/수정
]
