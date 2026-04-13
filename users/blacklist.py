"""
users/blacklist.py — Redis 기반 JWT 블랙리스트

add(jti, exp): JTI를 Redis에 등록, TTL = 토큰 남은 유효시간
is_blacklisted(jti): JTI가 블랙리스트에 있는지 확인

Redis DB 3 사용 (DB 0: Celery, DB 2: 레이트 리밋과 분리)
키 형식: bl:{jti}
"""
import time
import redis
from django.conf import settings

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = redis.from_url(settings.REDIS_BLACKLIST_URL)
    return _client


def add(jti: str, exp: int) -> None:
    """토큰 JTI를 블랙리스트에 추가. TTL은 토큰 만료까지 남은 초."""
    ttl = int(exp - time.time())
    if ttl > 0:
        _get_client().setex(f'bl:{jti}', ttl, '1')


def is_blacklisted(jti: str) -> bool:
    """JTI가 블랙리스트에 등록되어 있으면 True."""
    return bool(_get_client().exists(f'bl:{jti}'))
