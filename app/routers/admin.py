from fastapi import APIRouter, Depends, HTTPException, status

from app.database import pb
from app.dependencies import require_admin, _record_to_dict
from app.models.user import UserUpdateRequest
from app.models.application import ApplicationUpdateRequest
from app.models.admin import (
    InsightsRequest,
    OllamaPullRequest,
    OllamaSettingsResponse,
    OllamaSettingsUpdateRequest,
)
from app.services import metrics_service, security_service, ollama_client
from app.config import settings

router = APIRouter()


def _app_record_to_dict(r) -> dict:
    created = r.created
    if hasattr(created, "isoformat"):
        created = created.isoformat()
    return {
        "id": r.id,
        "userId": getattr(r, "user", ""),
        "userName": getattr(r, "user_name", ""),
        "projectName": getattr(r, "project_name", ""),
        "useCase": getattr(r, "use_case", ""),
        "requestedQuota": getattr(r, "requested_quota", 0) or 0,
        "status": getattr(r, "status", "pending"),
        "createdAt": str(created),
    }


@router.get("/users")
async def list_users(admin: dict = Depends(require_admin)):
    results = pb.collection("users").get_list(1, 200, {"sort": "-created"})
    return [_record_to_dict(r) for r in results.items]


@router.patch("/users/{user_id}")
async def update_user(user_id: str, body: UserUpdateRequest, admin: dict = Depends(require_admin)):
    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to update")
    try:
        pb.collection("users").update(user_id, update_data)
        record = pb.collection("users").get_one(user_id)
        return _record_to_dict(record)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/security-events")
async def security_events(admin: dict = Depends(require_admin)):
    return security_service.get_events()


@router.get("/metrics")
async def system_metrics(admin: dict = Depends(require_admin)):
    base = metrics_service.get_system_metrics()

    # Add request-level metrics from usage_logs
    active_requests = 0
    error_rate = 0.0
    avg_response_time = 0.0
    try:
        total = pb.collection("usage_logs").get_list(1, 1)
        total_count = total.total_items
        if total_count > 0:
            errors = pb.collection("usage_logs").get_list(1, 1, {"filter": 'isError=true'})
            error_rate = round((errors.total_items / total_count) * 100, 1)

            recent = pb.collection("usage_logs").get_list(1, 100, {"sort": "-created"})
            if recent.items:
                total_rt = sum(getattr(r, "response_time_ms", 0) or 0 for r in recent.items)
                avg_response_time = round(total_rt / len(recent.items), 1)
    except Exception:
        pass

    return {
        **base,
        "activeRequests": active_requests,
        "errorRate": error_rate,
        "avgResponseTime": avg_response_time,
    }


@router.get("/models/performance")
async def model_performance(admin: dict = Depends(require_admin)):
    """Compute model performance from usage_logs."""
    performance: list[dict] = []
    try:
        data = await ollama_client.list_models()
        models = data.get("models", [])

        for m in models:
            name = m.get("name", "")
            try:
                logs = pb.collection("usage_logs").get_list(
                    1, 100, {"filter": f'model="{name}"', "sort": "-created"}
                )
                items = logs.items
                total_tokens = sum((getattr(r, "total_tokens", 0) or 0) for r in items)
                total_time = sum((getattr(r, "response_time_ms", 0) or 0) for r in items)
                error_count = sum(1 for r in items if getattr(r, "is_error", False))
                count = len(items)

                tokens_per_sec = round(total_tokens / (total_time / 1000), 1) if total_time > 0 else 0
                avg_latency = round(total_time / count, 1) if count > 0 else 0
                err_rate = round((error_count / count) * 100, 1) if count > 0 else 0

                size_bytes = m.get("size", 0)
                gb = size_bytes / (1024 ** 3)
                mem_str = f"{gb:.1f}GB" if gb >= 1 else f"{size_bytes / (1024**2):.0f}MB"

                performance.append({
                    "name": name,
                    "tokensPerSec": tokens_per_sec,
                    "avgLatency": avg_latency,
                    "memoryUsage": mem_str,
                    "errorRate": err_rate,
                })
            except Exception:
                performance.append({
                    "name": name,
                    "tokensPerSec": 0,
                    "avgLatency": 0,
                    "memoryUsage": "Unknown",
                    "errorRate": 0,
                })
    except Exception:
        pass

    return performance


@router.post("/insights")
async def admin_insights(body: InsightsRequest, admin: dict = Depends(require_admin)):
    try:
        result = await ollama_client.chat({
            "model": "llama3:8b",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a senior DevOps engineer and security analyst. Provide concise, actionable insights for an LLM gateway service. Reply with 3 bullet points.",
                },
                {
                    "role": "user",
                    "content": f"Analyze these system statistics and provide 3 key management recommendations: {body.stats}",
                },
            ],
            "stream": False,
        })
        content = result.get("message", {}).get("content", "No insights generated.")
        return {"insights": content}
    except Exception:
        return {"insights": "Unable to generate insights. Ensure Ollama is running."}


@router.get("/applications")
async def list_all_applications(admin: dict = Depends(require_admin)):
    results = pb.collection("api_applications").get_list(1, 200, {"sort": "-created"})
    return [_app_record_to_dict(r) for r in results.items]


@router.patch("/applications/{app_id}")
async def update_application(
    app_id: str, body: ApplicationUpdateRequest, admin: dict = Depends(require_admin)
):
    try:
        record = pb.collection("api_applications").get_one(app_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    update_data = {"status": body.status}
    if body.adminNote:
        update_data["adminNote"] = body.adminNote

    # If approved, increase user quota
    if body.status == "approved":
        try:
            user_record = pb.collection("users").get_one(record.user)
            current_quota = getattr(user_record, "total_quota", 50000) or 50000
            requested = getattr(record, "requested_quota", 0) or 0
            pb.collection("users").update(record.user, {
                "totalQuota": current_quota + requested,
            })
        except Exception:
            pass

    pb.collection("api_applications").update(app_id, update_data)
    updated = pb.collection("api_applications").get_one(app_id)
    return _app_record_to_dict(updated)


def _get_system_setting(key: str, default: str = "") -> str:
    """시스템 설정 값을 가져옵니다."""
    try:
        results = pb.collection("system_settings").get_list(1, 1, {"filter": f'key="{key}"'})
        if results.items:
            return getattr(results.items[0], "value", default)
    except Exception:
        pass
    return default


def _set_system_setting(key: str, value: str, description: str = "") -> None:
    """시스템 설정 값을 저장합니다."""
    try:
        # 기존 설정이 있는지 확인
        results = pb.collection("system_settings").get_list(1, 1, {"filter": f'key="{key}"'})
        if results.items:
            # 업데이트
            pb.collection("system_settings").update(results.items[0].id, {"value": value})
        else:
            # 새로 생성
            pb.collection("system_settings").create({
                "key": key,
                "value": value,
                "description": description,
            })
    except Exception:
        pass


@router.get("/ollama-settings")
async def get_ollama_settings(admin: dict = Depends(require_admin)):
    """관리자용 Ollama 설정 조회"""
    ollama_url = _get_system_setting("ollama_base_url", settings.OLLAMA_BASE_URL)
    return OllamaSettingsResponse(ollamaBaseUrl=ollama_url)


@router.patch("/ollama-settings")
async def update_ollama_settings(
    body: OllamaSettingsUpdateRequest, admin: dict = Depends(require_admin)
):
    """관리자용 Ollama URL 업데이트"""
    _set_system_setting("ollama_base_url", body.ollamaBaseUrl, "Ollama 서버 베이스 URL")
    # 클라이언트 재생성을 위해 기존 클라이언트 닫기
    ollama_client.reset_client()
    return OllamaSettingsResponse(ollamaBaseUrl=body.ollamaBaseUrl)


@router.post("/models/pull")
async def pull_ollama_model(
    body: OllamaPullRequest, admin: dict = Depends(require_admin)
):
    """관리자용: Ollama에 새 모델 pull"""
    model_name = (body.name or "").strip()
    if not model_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Model name is required")

    try:
        result = await ollama_client.pull_model(model_name)
        return {"ok": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to pull model: {e}")
