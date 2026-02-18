"""
Redis 캐시 서비스
- Redis 미설정 시 silently pass (캐시 없이 정상 동작)
- 모든 메서드는 예외를 catch하여 캐시 장애가 서비스 장애로 전파되지 않도록 함

캐시 키 구조:
  auth:apikey:{key_hash}   → API Key 인증 결과 (user dict + _api_key_id), TTL 5분
  auth:user:{user_id}      → JWT 인증 결과 (user dict), TTL 5분
  reset:{user_id}:{date}   → 일일 리셋 완료 여부, TTL 자정까지
  config:ollama_url        → Ollama 서버 URL, TTL 10분
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not settings.REDIS_URL:
        return None
    try:
        import redis
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=1.0)
        _client.ping()
        logger.info("Redis cache connected")
    except Exception as e:
        logger.warning(f"Redis unavailable, running without cache: {e}")
        _client = None
    return _client


def get(key: str) -> Any | None:
    r = _get_client()
    if r is None:
        return None
    try:
        val = r.get(key)
        return json.loads(val) if val else None
    except Exception:
        return None


def set(key: str, value: Any, ttl: int = 300) -> None:
    r = _get_client()
    if r is None:
        return
    try:
        r.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


def delete(key: str) -> None:
    r = _get_client()
    if r is None:
        return
    try:
        r.delete(key)
    except Exception:
        pass


def delete_pattern(pattern: str) -> None:
    r = _get_client()
    if r is None:
        return
    try:
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)
    except Exception:
        pass


def _seconds_until_midnight() -> int:
    """자정까지 남은 초 (최소 60초)"""
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=23, minute=59, second=59, microsecond=0)
    diff = int((midnight - now).total_seconds())
    return max(diff, 60)


# ── 캐시 키 헬퍼 ──────────────────────────────────────────────────

def key_auth_apikey(key_hash: str) -> str:
    return f"auth:apikey:{key_hash}"


def key_auth_user(user_id: str) -> str:
    return f"auth:user:{user_id}"


def key_daily_reset(user_id: str, date: str) -> str:
    return f"reset:{user_id}:{date}"


def key_ollama_url() -> str:
    return "config:ollama_url"


# ── 도메인 캐시 함수 ──────────────────────────────────────────────

def get_cached_apikey_user(key_hash: str) -> dict | None:
    return get(key_auth_apikey(key_hash))


def set_cached_apikey_user(key_hash: str, user: dict) -> None:
    set(key_auth_apikey(key_hash), user, ttl=300)  # 5분


def get_cached_jwt_user(user_id: str) -> dict | None:
    return get(key_auth_user(user_id))


def set_cached_jwt_user(user_id: str, user: dict) -> None:
    set(key_auth_user(user_id), user, ttl=300)  # 5분


def invalidate_user(user_id: str) -> None:
    """유저 정보 변경 시 관련 캐시 전체 무효화"""
    delete(key_auth_user(user_id))
    delete_pattern(f"auth:apikey:*")  # key_hash → user_id 역매핑이 없으므로 패턴 삭제


def is_daily_reset_done(user_id: str, today: str) -> bool:
    return get(key_daily_reset(user_id, today)) is not None


def mark_daily_reset_done(user_id: str, today: str) -> None:
    set(key_daily_reset(user_id, today), 1, ttl=_seconds_until_midnight())


def get_cached_ollama_url() -> str | None:
    return get(key_ollama_url())


def set_cached_ollama_url(url: str) -> None:
    set(key_ollama_url(), url, ttl=600)  # 10분
