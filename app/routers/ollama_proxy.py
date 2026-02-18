import json
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.config import settings
from app.dependencies import get_api_key_user
from app.models.ollama import ChatRequest, ModelShowRequest
from app.services import ollama_client
from app.services.quota_service import check_and_deduct, reset_daily_if_needed
from app.database import pb

router = APIRouter()
openai_router = APIRouter()
ollama_native_router = APIRouter()


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
    model = body.model or settings.DEFAULT_MODEL

    # 스트리밍 요청 처리
    if body.stream:
        payload = {
            "model": model,
            "messages": [m.model_dump() for m in body.messages],
            "stream": True,
        }
        if body.options:
            payload["options"] = body.options

        start = time.time()
        token_state = {"prompt": 0, "completion": 0}

        async def generate():
            try:
                async for chunk in ollama_client.chat_stream(payload):
                    yield chunk
                    try:
                        data = json.loads(chunk)
                        if data.get("done"):
                            token_state["prompt"] = data.get("prompt_eval_count", 0) or 0
                            token_state["completion"] = data.get("eval_count", 0) or 0
                    except Exception:
                        pass
            except Exception as e:
                yield (json.dumps({"error": str(e)}) + "\n").encode()
            finally:
                total = token_state["prompt"] + token_state["completion"]
                elapsed = time.time() - start
                try:
                    check_and_deduct(user, total, user.get("_api_key_id"))
                except ValueError:
                    pass
                _log_usage(user, model, "/api/v1/chat", token_state["prompt"], token_state["completion"], elapsed, 200, request, False)

        return StreamingResponse(
            generate(),
            media_type="application/x-ndjson",
            headers={"X-Accel-Buffering": "no"},
        )

    # 일반(비스트리밍) 처리
    payload = {
        "model": model,
        "messages": [m.model_dump() for m in body.messages],
        "stream": False,
    }
    if body.options:
        payload["options"] = body.options

    start = time.time()
    try:
        result = await ollama_client.chat(payload)
    except Exception as e:
        _log_usage(user, model, "/api/v1/chat", 0, 0, time.time() - start, 502, request, True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Ollama error: {e}")

    prompt_tokens = result.get("prompt_eval_count", 0) or 0
    completion_tokens = result.get("eval_count", 0) or 0
    total_tokens = prompt_tokens + completion_tokens
    elapsed = time.time() - start

    try:
        check_and_deduct(user, total_tokens, user.get("_api_key_id"))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))

    _log_usage(user, model, "/api/v1/chat", prompt_tokens, completion_tokens, elapsed, 200, request, False)

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


# ── OpenAI Compatible Endpoints ──


@openai_router.post("/chat/completions")
async def openai_chat_completions(body: ChatRequest, request: Request, user: dict = Depends(get_api_key_user)):
    """OpenAI-compatible chat completions endpoint."""
    reset_daily_if_needed(user["id"])
    model = body.model or settings.DEFAULT_MODEL

    payload = {
        "model": model,
        "messages": [m.model_dump() for m in body.messages],
        "stream": False,
    }
    if body.options:
        payload["options"] = body.options

    start = time.time()
    try:
        result = await ollama_client.chat(payload)
    except Exception as e:
        _log_usage(user, model, "/v1/chat/completions", 0, 0, time.time() - start, 502, request, True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Ollama error: {e}")

    prompt_tokens = result.get("prompt_eval_count", 0) or 0
    completion_tokens = result.get("eval_count", 0) or 0
    total_tokens = prompt_tokens + completion_tokens
    elapsed = time.time() - start

    try:
        check_and_deduct(user, total_tokens, user.get("_api_key_id"))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))

    _log_usage(user, model, "/v1/chat/completions", prompt_tokens, completion_tokens, elapsed, 200, request, False)

    # Return OpenAI-compatible response format
    msg = result.get("message", {})
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": msg.get("role", "assistant"),
                    "content": msg.get("content", ""),
                },
                "finish_reason": result.get("done_reason", "stop"),
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
    }


@openai_router.get("/models")
async def openai_list_models(user: dict = Depends(get_api_key_user)):
    """OpenAI-compatible models list endpoint."""
    try:
        data = await ollama_client.list_models()
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Cannot reach Ollama")

    models = []
    for m in data.get("models", []):
        models.append({
            "id": m.get("name", ""),
            "object": "model",
            "created": int(time.time()),
            "owned_by": "ollama",
        })
    return {"object": "list", "data": models}


# ── Ollama Native Endpoints (for n8n Ollama node) ──


@ollama_native_router.get("/tags")
async def ollama_tags(user: dict = Depends(get_api_key_user)):
    """Ollama-native /api/tags endpoint for n8n compatibility."""
    try:
        data = await ollama_client.list_models()
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Cannot reach Ollama")
    return data


@ollama_native_router.post("/chat")
async def ollama_native_chat(body: ChatRequest, request: Request, user: dict = Depends(get_api_key_user)):
    """Ollama-native /api/chat endpoint for n8n compatibility."""
    reset_daily_if_needed(user["id"])
    model = body.model or settings.DEFAULT_MODEL

    payload = {
        "model": model,
        "messages": [m.model_dump() for m in body.messages],
        "stream": False,
    }
    if body.options:
        payload["options"] = body.options

    start = time.time()
    try:
        result = await ollama_client.chat(payload)
    except Exception as e:
        _log_usage(user, model, "/api/chat", 0, 0, time.time() - start, 502, request, True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Ollama error: {e}")

    prompt_tokens = result.get("prompt_eval_count", 0) or 0
    completion_tokens = result.get("eval_count", 0) or 0
    total_tokens = prompt_tokens + completion_tokens
    elapsed = time.time() - start

    try:
        check_and_deduct(user, total_tokens, user.get("_api_key_id"))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))

    _log_usage(user, model, "/api/chat", prompt_tokens, completion_tokens, elapsed, 200, request, False)

    return result


@ollama_native_router.post("/generate")
async def ollama_native_generate(request: Request, user: dict = Depends(get_api_key_user)):
    """Ollama-native /api/generate endpoint."""
    body = await request.json()
    start = time.time()
    try:
        result = await ollama_client.generate(body)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Ollama error: {e}")

    prompt_tokens = result.get("prompt_eval_count", 0) or 0
    completion_tokens = result.get("eval_count", 0) or 0
    total_tokens = prompt_tokens + completion_tokens
    elapsed = time.time() - start

    try:
        check_and_deduct(user, total_tokens, user.get("_api_key_id"))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))

    _log_usage(user, body.get("model", ""), "/api/generate", prompt_tokens, completion_tokens, elapsed, 200, request, False)

    return result
