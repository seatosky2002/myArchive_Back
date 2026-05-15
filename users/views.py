from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from . import blacklist
from .serializers import LoginSerializer, ProfileUpdateSerializer, RegisterSerializer, UserSerializer
from .throttles import LoginRateThrottle, RegisterRateThrottle

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
    throttle_classes = (RegisterRateThrottle,)

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
    throttle_classes = (LoginRateThrottle,)

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
    - 쿠키의 refresh 토큰 → Redis 블랙리스트 등록 + 쿠키 삭제
    - 헤더의 access 토큰  → Redis 블랙리스트 등록 (1시간 내 재사용 차단)
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        # access 토큰 블랙리스트 등록
        access_token = request.auth
        if access_token:
            blacklist.add(access_token['jti'], access_token['exp'])

        # refresh 토큰 블랙리스트 등록
        refresh_str = request.COOKIES.get(REFRESH_COOKIE)
        if refresh_str:
            try:
                refresh = RefreshToken(refresh_str)
                blacklist.add(refresh['jti'], refresh['exp'])
            except TokenError:
                pass

        response = Response({'detail': '로그아웃 되었습니다.'}, status=status.HTTP_200_OK)
        response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
        return response


class CookieTokenRefreshView(APIView):
    """
    POST /api/users/token/refresh/
    쿠키의 refresh 토큰으로 새 access 발급.
    이전 refresh JTI는 블랙리스트에 추가하고 새 refresh를 쿠키로 재설정 (rotation).
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        refresh_str = request.COOKIES.get(REFRESH_COOKIE)
        if not refresh_str:
            return Response({'detail': 'refresh 토큰이 없습니다.'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            refresh = RefreshToken(refresh_str)
        except TokenError:
            return Response({'detail': '유효하지 않은 refresh 토큰입니다.'}, status=status.HTTP_401_UNAUTHORIZED)

        # 블랙리스트 확인
        if blacklist.is_blacklisted(refresh['jti']):
            return Response({'detail': '만료된 refresh 토큰입니다.'}, status=status.HTTP_401_UNAUTHORIZED)

        # 이전 refresh 블랙리스트 등록 (rotation)
        blacklist.add(refresh['jti'], refresh['exp'])

        # 새 토큰 발급
        new_refresh = RefreshToken.for_user(refresh.user_token if hasattr(refresh, 'user_token') else _get_user_from_refresh(refresh))
        response = Response({'access': str(new_refresh.access_token)})
        _set_refresh_cookie(response, new_refresh)
        return response


def _get_user_from_refresh(refresh):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.get(pk=refresh['user_id'])


class MeView(APIView):
    """
    GET    /api/users/me/ → 내 프로필 조회
    PUT    /api/users/me/ → 내 프로필 수정 (nickname, profile_img_url)
    DELETE /api/users/me/ → 계정 탈퇴 (비밀번호 확인 필요)
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

    def delete(self, request):
        password = request.data.get('password', '')
        if not request.user.check_password(password):
            return Response({'detail': '비밀번호가 올바르지 않습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        # 현재 토큰 블랙리스트 등록
        access_token = request.auth
        if access_token:
            blacklist.add(access_token['jti'], access_token['exp'])
        refresh_str = request.COOKIES.get(REFRESH_COOKIE)
        if refresh_str:
            try:
                refresh = RefreshToken(refresh_str)
                blacklist.add(refresh['jti'], refresh['exp'])
            except TokenError:
                pass

        request.user.delete()
        response = Response({'detail': '계정이 삭제되었습니다.'}, status=status.HTTP_200_OK)
        response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
        return response


class PasswordChangeView(APIView):
    """
    PUT /api/users/me/password/ → 비밀번호 변경 (현재 비밀번호 확인 필요)
    """
    permission_classes = (IsAuthenticated,)

    def put(self, request):
        current  = request.data.get('current_password', '')
        new_pw   = request.data.get('new_password', '')

        if not current or not new_pw:
            return Response(
                {'detail': 'current_password와 new_password가 필요합니다.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not request.user.check_password(current):
            return Response({'detail': '현재 비밀번호가 올바르지 않습니다.'}, status=status.HTTP_400_BAD_REQUEST)
        if len(new_pw) < 8:
            return Response({'detail': '새 비밀번호는 8자 이상이어야 합니다.'}, status=status.HTTP_400_BAD_REQUEST)
        if current == new_pw:
            return Response({'detail': '새 비밀번호가 현재 비밀번호와 동일합니다.'}, status=status.HTTP_400_BAD_REQUEST)

        request.user.set_password(new_pw)
        request.user.save(update_fields=['password'])
        return Response({'detail': '비밀번호가 변경되었습니다.'})


class PasswordResetView(APIView):
    """
    POST /api/users/password-reset/
    가입된 이메일로 재설정 링크 발송. 이메일 미존재 시에도 200 반환 (계정 존재 여부 노출 방지).
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        email = request.data.get('email', '').strip()
        if not email:
            return Response({'detail': 'email이 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

        User = get_user_model()
        try:
            user = User.objects.get(email=email)
            uid   = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')}/reset-password/{uid}/{token}/"
            send_mail(
                subject='[MyMemoryMap] 비밀번호 재설정',
                message=f'아래 링크를 클릭해 비밀번호를 재설정하세요 (24시간 유효):\n\n{reset_url}',
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@mymemorymap.com'),
                recipient_list=[email],
                fail_silently=True,
            )
        except User.DoesNotExist:
            pass  # 계정 존재 여부 노출 방지

        return Response({'detail': '이메일이 전송되었습니다. 받은 편지함을 확인해주세요.'})


class PasswordResetConfirmView(APIView):
    """
    POST /api/users/password-reset/confirm/
    uid + token 검증 후 새 비밀번호로 변경.
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        uid      = request.data.get('uid', '')
        token    = request.data.get('token', '')
        new_pw   = request.data.get('new_password', '')

        if not uid or not token or not new_pw:
            return Response({'detail': 'uid, token, new_password가 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)
        if len(new_pw) < 8:
            return Response({'detail': '비밀번호는 8자 이상이어야 합니다.'}, status=status.HTTP_400_BAD_REQUEST)

        User = get_user_model()
        try:
            pk   = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=pk)
        except (User.DoesNotExist, ValueError, TypeError):
            return Response({'detail': '유효하지 않은 링크입니다.'}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({'detail': '링크가 만료되었거나 유효하지 않습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_pw)
        user.save(update_fields=['password'])
        return Response({'detail': '비밀번호가 재설정되었습니다.'})
