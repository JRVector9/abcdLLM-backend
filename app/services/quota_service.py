from datetime import datetime, timezone

from app.database import pb


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def check_and_deduct(user: dict, tokens_used: int, api_key_id: str | None = None) -> None:
    """Check quota and deduct tokens. Raises ValueError if over quota."""
    user_id = user["id"]
    today = _today()

    # ── API 키별 할당량 체크 (우선순위) ──
    if api_key_id:
        try:
            key_record = pb.collection("api_keys").get_one(api_key_id)

            # API 키의 일일/총 할당량 (camelCase/snake_case 호환)
            key_daily_quota = (
                getattr(key_record, "dailyTokens", None) or
                getattr(key_record, "daily_tokens", None) or 0
            )
            key_total_quota = (
                getattr(key_record, "totalTokens", None) or
                getattr(key_record, "total_tokens", None) or 0
            )

            # 현재 사용량
            last_reset = str(getattr(key_record, "lastResetDate", "") or getattr(key_record, "last_reset_date", "") or "")
            used_tokens = getattr(key_record, "usedTokens", 0) or getattr(key_record, "used_tokens", 0) or 0
            total_used_tokens = getattr(key_record, "totalUsedTokens", 0) or getattr(key_record, "total_used_tokens", 0) or 0

            # 날짜가 바뀌면 일일 사용량 리셋
            if last_reset and not last_reset.startswith(today):
                used_tokens = 0

            # API 키별 일일 할당량 체크
            if key_daily_quota > 0:
                if used_tokens + tokens_used > key_daily_quota:
                    raise ValueError(f"API key daily quota exceeded ({used_tokens}/{key_daily_quota})")

            # API 키별 총 할당량 체크
            if key_total_quota > 0:
                if total_used_tokens + tokens_used > key_total_quota:
                    raise ValueError(f"API key total quota exceeded ({total_used_tokens}/{key_total_quota})")

        except ValueError:
            # 할당량 초과 에러는 그대로 전파
            raise
        except Exception as e:
            # API 키 조회 실패 시 로깅하고 사용자 레벨 체크로 진행
            print(f"Warning: API key quota check failed: {e}")
            pass

    # ── 사용자 레벨 할당량 체크 ──
    record = pb.collection("users").get_one(user_id)
    daily_usage = getattr(record, "dailyUsage", 0) or getattr(record, "daily_usage", 0) or 0
    daily_quota = getattr(record, "dailyQuota", None) or getattr(record, "daily_quota", None) or 5000
    total_usage = getattr(record, "totalUsage", 0) or getattr(record, "total_usage", 0) or 0
    total_quota = getattr(record, "totalQuota", None) or getattr(record, "total_quota", None) or 50000

    if daily_usage + tokens_used > daily_quota:
        raise ValueError(f"User daily quota exceeded ({daily_usage}/{daily_quota})")
    if total_usage + tokens_used > total_quota:
        raise ValueError(f"User total quota exceeded ({total_usage}/{total_quota})")

    # ── 사용자 사용량 업데이트 ──
    pb.collection("users").update(user_id, {
        "dailyUsage": daily_usage + tokens_used,
        "totalUsage": total_usage + tokens_used,
        "lastActive": datetime.now(timezone.utc).isoformat(),
    })

    # ── API 키 사용량 업데이트 ──
    if api_key_id:
        try:
            key_record = pb.collection("api_keys").get_one(api_key_id)
            last_reset = str(getattr(key_record, "lastResetDate", "") or getattr(key_record, "last_reset_date", "") or "")
            used_requests = getattr(key_record, "usedRequests", 0) or getattr(key_record, "used_requests", 0) or 0
            used_tokens = getattr(key_record, "usedTokens", 0) or getattr(key_record, "used_tokens", 0) or 0
            total_used_tokens = getattr(key_record, "totalUsedTokens", 0) or getattr(key_record, "total_used_tokens", 0) or 0

            # 날짜가 바뀌면 일일 사용량 리셋
            if last_reset and not last_reset.startswith(today):
                used_requests = 0
                used_tokens = 0

            pb.collection("api_keys").update(api_key_id, {
                "usedRequests": used_requests + 1,
                "usedTokens": used_tokens + tokens_used,
                "totalUsedTokens": total_used_tokens + tokens_used,
                "lastResetDate": today,
            })
        except Exception as e:
            print(f"Warning: API key usage update failed: {e}")
            pass


def reset_daily_if_needed(user_id: str) -> None:
    """Reset daily usage if it's a new day. Called at request time."""
    try:
        record = pb.collection("users").get_one(user_id)
        last_active = getattr(record, "lastActive", "") or getattr(record, "last_active", "") or ""
        today = _today()

        if last_active:
            # ISO 8601 형식에서 날짜 부분만 추출 (YYYY-MM-DD)
            last_date = str(last_active)[:10]
            if last_date != today:
                # 새로운 날짜이면 일일 사용량 리셋
                pb.collection("users").update(user_id, {
                    "dailyUsage": 0,
                    "lastActive": datetime.now(timezone.utc).isoformat(),
                })
        else:
            # last_active가 없으면 초기화
            pb.collection("users").update(user_id, {
                "lastActive": datetime.now(timezone.utc).isoformat(),
            })
    except Exception as e:
        print(f"Warning: Daily reset failed: {e}")
        pass
