from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from .serializers import LoginSerializer, ProfileUpdateSerializer, RegisterSerializer, UserSerializer

REFRESH_COOKIE = 'refresh'
REFRESH_COOKIE_PATH = '/api/users/token/'


def _set_refresh_cookie(response, refresh_token):
    """refresh 토큰을 httpOnly 쿠키로 설정"""
    response.set_cookie(
        REFRESH_COOKIE,
        value=str(refresh_token),
        max_age=7 * 24 * 60 * 60,  # 7일
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        samesite='Lax',
        secure=not settings.DEBUG,  # 프로덕션에서만 Secure
    )


class RegisterView(APIView):
    """
    POST /api/users/register/
    회원가입 → access는 body, refresh는 httpOnly 쿠키로 반환.
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        response = Response(
            {'access': str(refresh.access_token), 'user': UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )
        _set_refresh_cookie(response, refresh)
        return response


class LoginView(APIView):
    """
    POST /api/users/login/
    email + password → access는 body, refresh는 httpOnly 쿠키로 반환.
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        response = Response(
            {'access': str(refresh.access_token), 'user': UserSerializer(user).data},
            status=status.HTTP_200_OK,
        )
        _set_refresh_cookie(response, refresh)
        return response


class LogoutView(APIView):
    """
    POST /api/users/logout/
    쿠키의 refresh 토큰을 블랙리스트 처리 후 쿠키 삭제.
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        refresh_token = request.COOKIES.get(REFRESH_COOKIE)
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except TokenError:
                pass
        response = Response({'detail': '로그아웃 되었습니다.'}, status=status.HTTP_200_OK)
        response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
        return response


class CookieTokenRefreshView(APIView):
    """
    POST /api/users/token/refresh/
    쿠키의 refresh 토큰으로 새 access 발급.
    ROTATE_REFRESH_TOKENS=True면 새 refresh도 쿠키로 재설정.
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        refresh_token = request.COOKIES.get(REFRESH_COOKIE)
        if not refresh_token:
            return Response({'detail': 'refresh 토큰이 없습니다.'}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = TokenRefreshSerializer(data={'refresh': refresh_token})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            return Response({'detail': str(e)}, status=status.HTTP_401_UNAUTHORIZED)

        response = Response({'access': serializer.validated_data['access']})

        # ROTATE_REFRESH_TOKENS=True일 때 새 refresh를 쿠키로 재설정
        if 'refresh' in serializer.validated_data:
            _set_refresh_cookie(response, serializer.validated_data['refresh'])

        return response


class MeView(APIView):
    """
    GET  /api/users/me/ → 내 프로필 조회
    PUT  /api/users/me/ → 내 프로필 수정 (nickname, profile_img_url)
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def put(self, request):
        serializer = ProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data)
