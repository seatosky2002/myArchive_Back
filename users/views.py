from django.contrib.auth import login, logout
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, ProfileUpdateSerializer, RegisterSerializer, UserSerializer


class RegisterView(APIView):
    """
    POST /api/users/register/
    회원가입 → Token 발급 → { token, user } 반환.
    프론트는 token을 localStorage에 저장하여 이후 요청에 사용.
    인증 없이 접근 가능 (AllowAny).
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Token 발급 (get_or_create로 중복 방지)
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {'token': token.key, 'user': UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """
    POST /api/users/login/
    email + password → Token 발급 → { token, user } 반환.
    인증 없이 접근 가능 (AllowAny).
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {'token': token.key, 'user': UserSerializer(user).data},
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """
    POST /api/users/logout/
    서버 측 Token 삭제.
    프론트는 localStorage의 token도 함께 삭제해야 함.
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        # Token 삭제로 서버 측 인증 무효화
        request.user.auth_token.delete()
        return Response({'detail': '로그아웃 되었습니다.'}, status=status.HTTP_200_OK)


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
