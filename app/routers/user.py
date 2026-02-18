import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.database import pb
from app.dependencies import get_current_user
from app.services import ollama_client
from app.services import metrics_service
from app.services import cache

router = APIRouter()

_DASHBOARD_TTL = 30  # 30초 캐시


@router.get("/dashboard")
async def dashboard(user: dict = Depends(get_current_user)):
    cache_key = f"dashboard:{user['id']}"

    # Redis 캐시 히트 → 즉시 반환
    cached = cache.get(cache_key)
    if cached:
        cached["user"] = user  # user 정보는 항상 신선하게
        return cached

    # Ollama list_models 비동기 시작 (DB 쿼리와 병렬 실행)
    ollama_task = asyncio.create_task(ollama_client.list_models())

    # DB 쿼리 (동기, 순차)
    recent_usage: list[dict] = []
    total_requests = 0
    try:
        logs = pb.collection("usage_logs").get_list(
            1, 100,
            {"filter": f'user="{user["id"]}"', "sort": "-created"},
        )
        total_requests = logs.total_items  # 두 번째 쿼리 제거 — 같은 응답에서 추출

        by_date: dict[str, dict] = {}
        for log in logs.items:
            date = str(log.created)[:10]
            if date not in by_date:
                by_date[date] = {"date": date, "requests": 0, "tokens": 0, "responseTime": 0}
            by_date[date]["requests"] += 1
            by_date[date]["tokens"] += getattr(log, "total_tokens", 0) or 0
            by_date[date]["responseTime"] += getattr(log, "response_time_ms", 0) or 0
        for d in by_date.values():
            if d["requests"] > 0:
                d["responseTime"] = d["responseTime"] // d["requests"]
        recent_usage = sorted(by_date.values(), key=lambda x: x["date"])[-7:]
    except Exception:
        pass

    # DB 쿼리가 끝난 후 Ollama 결과 await (이미 실행 중이었으므로 대기 시간 최소화)
    active_models = 0
    try:
        models_data = await ollama_task
        active_models = len(models_data.get("models", []))
    except Exception:
        pass

    result = {
        "recentUsage": recent_usage,
        "activeModels": active_models,
        "totalRequests": total_requests,
    }

    # Redis 캐싱 (user 제외 — 항상 신선하게 유지)
    cache.set(cache_key, result, ttl=_DASHBOARD_TTL)

    return {**result, "user": user}


@router.get("/quota")
async def quota(user: dict = Depends(get_current_user)):
    record = pb.collection("users").get_one(user["id"])
    return {
        "dailyUsage": getattr(record, "daily_usage", 0) or 0,
        "dailyQuota": getattr(record, "daily_quota", 5000) or 5000,
        "totalUsage": getattr(record, "total_usage", 0) or 0,
        "totalQuota": getattr(record, "total_quota", 50000) or 50000,
        "resetTime": "00:00 UTC",
    }
