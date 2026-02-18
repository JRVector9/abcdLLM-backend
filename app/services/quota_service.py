from datetime import datetime, timezone

from app.database import pb
from app.services import cache


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def check_and_deduct(user: dict, tokens_used: int, api_key_id: str | None = None) -> None:
    """Check quota and deduct tokens. Raises ValueError if over quota.

    user dict에 이미 quota 정보가 있으므로 DB 재조회 없이 사용.
    write 후 캐시 무효화.
    """
    user_id = user["id"]
    daily_usage = user.get("dailyUsage", 0) or 0
    daily_quota = user.get("dailyQuota", 5000) or 5000
    total_usage = user.get("usage", 0) or 0
    total_quota = user.get("totalQuota", 50000) or 50000

    if daily_usage + tokens_used > daily_quota:
        raise ValueError(f"Daily quota exceeded ({daily_usage}/{daily_quota})")
    if total_usage + tokens_used > total_quota:
        raise ValueError(f"Total quota exceeded ({total_usage}/{total_quota})")

    # DB 업데이트
    pb.collection("users").update(user_id, {
        "dailyUsage": daily_usage + tokens_used,
        "totalUsage": total_usage + tokens_used,
        "lastActive": datetime.now(timezone.utc).isoformat(),
    })

    # 캐시 무효화 (다음 요청에서 신선한 데이터 사용)
    cache.invalidate_user(user_id)

    # API Key usage 업데이트
    if api_key_id:
        try:
            key_record = pb.collection("api_keys").get_one(api_key_id)
            last_reset = str(getattr(key_record, "lastResetDate", "") or getattr(key_record, "last_reset_date", "") or "")
            today = _today()
            used_requests = getattr(key_record, "usedRequests", None) or getattr(key_record, "used_requests", None) or 0
            used_tokens = getattr(key_record, "usedTokens", None) or getattr(key_record, "used_tokens", None) or 0
            total_used_tokens = getattr(key_record, "totalUsedTokens", None) or getattr(key_record, "total_used_tokens", None) or 0

            if not last_reset.startswith(today):
                used_requests = 0
                used_tokens = 0

            pb.collection("api_keys").update(api_key_id, {
                "usedRequests": used_requests + 1,
                "usedTokens": used_tokens + tokens_used,
                "totalUsedTokens": total_used_tokens + tokens_used,
                "lastResetDate": today,
            })
        except Exception:
            pass


def reset_daily_if_needed(user_id: str) -> None:
    """Reset daily usage if it's a new day. Called at request time.

    Redis 캐시로 같은 날 중복 체크 방지.
    """
    today = _today()

    # 오늘 이미 체크했으면 스킵
    if cache.is_daily_reset_done(user_id, today):
        return

    try:
        record = pb.collection("users").get_one(user_id)
        last_active = getattr(record, "lastActive", "") or getattr(record, "last_active", "") or ""

        if last_active:
            last_date = str(last_active)[:10]
            if last_date != today:
                pb.collection("users").update(user_id, {
                    "dailyUsage": 0,
                    "lastActive": datetime.now(timezone.utc).isoformat(),
                })
                cache.invalidate_user(user_id)
        else:
            pb.collection("users").update(user_id, {
                "lastActive": datetime.now(timezone.utc).isoformat(),
            })
            cache.invalidate_user(user_id)

        # 오늘 체크 완료 표시 (자정까지 캐시)
        cache.mark_daily_reset_done(user_id, today)
    except Exception:
        pass
