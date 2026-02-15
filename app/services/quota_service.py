from datetime import datetime, timezone

from app.database import pb


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def check_and_deduct(user: dict, tokens_used: int, api_key_id: str | None = None) -> None:
    """Check quota and deduct tokens. Raises ValueError if over quota."""
    user_id = user["id"]
    record = pb.collection("users").get_one(user_id)

    # camelCase/snake_case 호환
    daily_usage = getattr(record, "dailyUsage", None) or getattr(record, "daily_usage", None) or 0
    daily_quota = getattr(record, "dailyQuota", None) or getattr(record, "daily_quota", None) or 5000
    total_usage = getattr(record, "totalUsage", None) or getattr(record, "total_usage", None) or 0
    total_quota = getattr(record, "totalQuota", None) or getattr(record, "total_quota", None) or 50000

    if daily_usage + tokens_used > daily_quota:
        raise ValueError(f"Daily quota exceeded ({daily_usage}/{daily_quota})")
    if total_usage + tokens_used > total_quota:
        raise ValueError(f"Total quota exceeded ({total_usage}/{total_quota})")

    # 사용량 업데이트 + lastActive 추가 (일일 리셋용)
    pb.collection("users").update(user_id, {
        "dailyUsage": daily_usage + tokens_used,
        "totalUsage": total_usage + tokens_used,
        "lastActive": datetime.now(timezone.utc).isoformat(),
    })

    # Update API key usage if applicable
    if api_key_id:
        try:
            key_record = pb.collection("api_keys").get_one(api_key_id)
            # camelCase/snake_case 호환
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
    """Reset daily usage if it's a new day. Called at request time."""
    try:
        record = pb.collection("users").get_one(user_id)
        # camelCase/snake_case 호환
        last_active = getattr(record, "lastActive", "") or getattr(record, "last_active", "") or ""
        today = _today()

        if last_active:
            last_date = str(last_active)[:10]
            if last_date != today:
                pb.collection("users").update(user_id, {
                    "dailyUsage": 0,
                    "lastActive": datetime.now(timezone.utc).isoformat(),
                })
        else:
            # lastActive가 없으면 초기화
            pb.collection("users").update(user_id, {
                "lastActive": datetime.now(timezone.utc).isoformat(),
            })
    except Exception:
        pass
