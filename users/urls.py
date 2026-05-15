from django.urls import path
from .views import (
    CookieTokenRefreshView, LoginView, LogoutView,
    MeView, RegisterView, PasswordChangeView,
    PasswordResetView, PasswordResetConfirmView,
)

urlpatterns = [
    path('register/',               RegisterView.as_view()),             # 회원가입
    path('login/',                  LoginView.as_view()),                # 로그인
    path('logout/',                 LogoutView.as_view()),               # 로그아웃
    path('token/refresh/',          CookieTokenRefreshView.as_view()),   # access 갱신
    path('me/',                     MeView.as_view()),                   # 프로필 조회/수정/탈퇴
    path('me/password/',            PasswordChangeView.as_view()),       # 비밀번호 변경
    path('password-reset/',         PasswordResetView.as_view()),        # 비밀번호 재설정 요청
    path('password-reset/confirm/', PasswordResetConfirmView.as_view()), # 비밀번호 재설정 확인
]
