from datetime import datetime, timezone

from app.database import pb


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def check_and_deduct(user: dict, tokens_used: int, api_key_id: str | None = None) -> None:
    """Check quota and deduct tokens. Raises ValueError if over quota."""
    user_id = user["id"]
    record = pb.collection("users").get_one(user_id)
    daily_usage = getattr(record, "daily_usage", 0) or 0
    daily_quota = getattr(record, "daily_quota", 5000) or 5000
    total_usage = getattr(record, "total_usage", 0) or 0
    total_quota = getattr(record, "total_quota", 50000) or 50000

    if daily_usage + tokens_used > daily_quota:
        raise ValueError(f"Daily quota exceeded ({daily_usage}/{daily_quota})")
    if total_usage + tokens_used > total_quota:
        raise ValueError(f"Total quota exceeded ({total_usage}/{total_quota})")

    pb.collection("users").update(user_id, {
        "dailyUsage": daily_usage + tokens_used,
        "totalUsage": total_usage + tokens_used,
    })

    # Update API key usage if applicable
    if api_key_id:
        try:
            key_record = pb.collection("api_keys").get_one(api_key_id)
            last_reset = str(getattr(key_record, "last_reset_date", "") or "")
            today = _today()
            used_requests = getattr(key_record, "used_requests", 0) or 0
            used_tokens = getattr(key_record, "used_tokens", 0) or 0
            total_used_tokens = getattr(key_record, "total_used_tokens", 0) or 0

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
        last_active = getattr(record, "last_active", "")
        if last_active:
            last_date = str(last_active)[:10]
            today = _today()
            if last_date != today:
                pb.collection("users").update(user_id, {"dailyUsage": 0})
    except Exception:
        pass
