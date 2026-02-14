from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.database import pb
from app.dependencies import get_current_user
from app.services import ollama_client

router = APIRouter()


@router.get("/dashboard")
async def dashboard(user: dict = Depends(get_current_user)):
    # Recent usage from usage_logs
    recent_usage: list[dict] = []
    try:
        logs = pb.collection("usage_logs").get_list(
            1, 100,
            {"filter": f'user="{user["id"]}"', "sort": "-created"},
        )
        # Aggregate by date
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

    # Active models count
    active_models = 0
    try:
        data = await ollama_client.list_models()
        active_models = len(data.get("models", []))
    except Exception:
        pass

    # Total requests
    total_requests = 0
    try:
        results = pb.collection("usage_logs").get_list(
            1, 1,
            {"filter": f'user="{user["id"]}"'},
        )
        total_requests = results.total_items
    except Exception:
        pass

    return {
        "user": user,
        "recentUsage": recent_usage,
        "activeModels": active_models,
        "totalRequests": total_requests,
    }


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
