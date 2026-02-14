import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.dependencies import get_api_key_user
from app.models.ollama import ChatRequest, ModelShowRequest
from app.services import ollama_client
from app.services.quota_service import check_and_deduct, reset_daily_if_needed
from app.database import pb

router = APIRouter()


def _format_bytes(n: int) -> str:
    if not n:
        return "Unknown"
    gb = n / (1024 ** 3)
    if gb >= 1:
        return f"{gb:.1f} GB"
    mb = n / (1024 ** 2)
    return f"{mb:.0f} MB"


def _format_relative(date_str: str) -> str:
    if not date_str:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt
        hours = int(diff.total_seconds() // 3600)
        if hours < 1:
            return "Just now"
        if hours < 24:
            return f"{hours} hours ago"
        days = hours // 24
        if days < 7:
            return f"{days} days ago"
        if days < 30:
            return f"{days // 7} weeks ago"
        return f"{days // 30} months ago"
    except Exception:
        return "Unknown"


@router.post("/chat")
async def chat(body: ChatRequest, request: Request, user: dict = Depends(get_api_key_user)):
    reset_daily_if_needed(user["id"])

    payload = {
        "model": body.model,
        "messages": [m.model_dump() for m in body.messages],
        "stream": False,
    }
    if body.options:
        payload["options"] = body.options

    start = time.time()
    try:
        result = await ollama_client.chat(payload)
    except Exception as e:
        _log_usage(user, body.model, "/api/v1/chat", 0, 0, time.time() - start, 502, request, True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Ollama error: {e}")

    prompt_tokens = result.get("prompt_eval_count", 0) or 0
    completion_tokens = result.get("eval_count", 0) or 0
    total_tokens = prompt_tokens + completion_tokens
    elapsed = time.time() - start

    try:
        check_and_deduct(user, total_tokens, user.get("_api_key_id"))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))

    _log_usage(user, body.model, "/api/v1/chat", prompt_tokens, completion_tokens, elapsed, 200, request, False)

    return result


@router.get("/models")
async def list_models(user: dict = Depends(get_api_key_user)):
    try:
        data = await ollama_client.list_models()
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Cannot reach Ollama")

    models = []
    for m in data.get("models", []):
        models.append({
            "name": m.get("name", ""),
            "size": _format_bytes(m.get("size", 0)),
            "modified": _format_relative(m.get("modified_at", "")),
            "parameterCount": (m.get("details") or {}).get("parameter_size"),
        })
    return models


@router.post("/models/show")
async def show_model(body: ModelShowRequest, user: dict = Depends(get_api_key_user)):
    try:
        return await ollama_client.show_model(body.name)
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Cannot reach Ollama")


@router.get("/health")
async def ollama_health():
    ok = await ollama_client.health_check()
    return {"status": "ok" if ok else "unreachable"}


def _log_usage(
    user: dict, model: str, endpoint: str,
    prompt_tokens: int, completion_tokens: int,
    elapsed: float, status_code: int, request: Request, is_error: bool,
) -> None:
    try:
        pb.collection("usage_logs").create({
            "user": user["id"],
            "apiKey": user.get("_api_key_id", ""),
            "model": model,
            "endpoint": endpoint,
            "promptTokens": prompt_tokens,
            "completionTokens": completion_tokens,
            "totalTokens": prompt_tokens + completion_tokens,
            "responseTimeMs": int(elapsed * 1000),
            "statusCode": status_code,
            "ip": request.client.host if request.client else "",
            "isError": is_error,
        })
    except Exception:
        pass
