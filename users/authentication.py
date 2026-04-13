"""
users/authentication.py — 블랙리스트 검사 커스텀 JWT 인증

모든 인증 요청에서 access 토큰의 JTI가 Redis 블랙리스트에 있는지 확인.
로그아웃 후 access 토큰(1h 이내)으로 재접근 시 즉시 차단.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

from . import blacklist


class BlacklistAwareJWTAuthentication(JWTAuthentication):
    def get_validated_token(self, raw_token):
        token = super().get_validated_token(raw_token)
        jti = token.get('jti')
        if jti and blacklist.is_blacklisted(jti):
            raise InvalidToken('로그아웃된 토큰입니다.')
        return token
