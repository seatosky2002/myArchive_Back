from django.contrib.auth import login, logout
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, ProfileUpdateSerializer, RegisterSerializer, UserSerializer


class RegisterView(APIView):
    """
    POST /api/users/register/
    회원가입 → 생성 성공 시 자동 로그인 후 유저 정보 반환.
    인증 없이 접근 가능 (AllowAny).
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # 가입 즉시 로그인 처리
        login(request, user)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """
    POST /api/users/login/
    email + password → 세션 인증 → 유저 정보 반환.
    인증 없이 접근 가능 (AllowAny).
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        login(request, user)
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    POST /api/users/logout/
    세션 삭제 후 로그아웃.
    로그인 상태에서만 접근 가능.
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        logout(request)
        return Response({'detail': '로그아웃 되었습니다.'}, status=status.HTTP_200_OK)


class MeView(APIView):
    """
    GET  /api/users/me/ → 내 프로필 조회
    PUT  /api/users/me/ → 내 프로필 수정 (nickname, profile_img_url)
    로그인 상태에서만 접근 가능.
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        # request.user는 현재 로그인한 유저 → 본인 정보만 반환
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def put(self, request):
        serializer = ProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,   # 일부 필드만 수정 허용 (PATCH처럼 동작)
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data)
