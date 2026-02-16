import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import pb
from app.dependencies import get_current_user, API_KEY_PREFIX
from app.models.api_key import ApiKeyCreateRequest

router = APIRouter()


def _generate_api_key() -> str:
    return f"{API_KEY_PREFIX}{secrets.token_hex(24)}"


def _key_to_response(record, plain_key: str | None = None) -> dict:
    created = record.created
    if hasattr(created, "isoformat"):
        created = created.isoformat()
    # Try both camelCase and snake_case for compatibility
    stored_key = getattr(record, "keyPlain", None) or getattr(record, "key_plain", None) or ""
    prefix = getattr(record, "keyPrefix", "") or getattr(record, "key_prefix", "") or ""
    return {
        "id": record.id,
        "name": getattr(record, "name", ""),
        "key": plain_key or stored_key or (prefix + "..."),
        "createdAt": str(created),
        # Limits
        "dailyRequests": getattr(record, "daily_requests", 0) or 0,
        "dailyTokens": getattr(record, "daily_tokens", 0) or 0,
        "totalTokens": getattr(record, "total_tokens", 0) or 0,
        # Actual usage
        "usedRequests": getattr(record, "used_requests", 0) or 0,
        "usedTokens": getattr(record, "used_tokens", 0) or 0,
        "totalUsedTokens": getattr(record, "total_used_tokens", 0) or 0,
        "lastResetDate": str(getattr(record, "last_reset_date", "") or ""),
    }


@router.get("")
async def list_keys(user: dict = Depends(get_current_user)):
    results = pb.collection("api_keys").get_list(1, 50, {"filter": f'user="{user["id"]}"'})
    return [_key_to_response(r) for r in results.items]


MAX_KEYS_PER_USER = 1


@router.post("")
async def create_key(body: ApiKeyCreateRequest, user: dict = Depends(get_current_user)):
    existing = pb.collection("api_keys").get_list(1, 1, {"filter": f'user="{user["id"]}"'})
    if existing.total_items >= MAX_KEYS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"API 키는 최대 {MAX_KEYS_PER_USER}개까지 생성할 수 있습니다",
        )
    plain_key = _generate_api_key()
    key_hash = hashlib.sha256(plain_key.encode()).hexdigest()

    record = pb.collection("api_keys").create({
        "user": user["id"],
        "name": body.name,
        "keyHash": key_hash,
        "keyPrefix": plain_key[:12],
        "keyPlain": plain_key,
        "dailyRequests": body.dailyRequests,
        "dailyTokens": body.dailyTokens,
        "totalTokens": body.totalTokens,
        "usedRequests": 0,
        "usedTokens": 0,
        "totalUsedTokens": 0,
        "lastResetDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "isActive": True,
    })
    return _key_to_response(record, plain_key)


@router.delete("/{key_id}")
async def delete_key(key_id: str, user: dict = Depends(get_current_user)):
    try:
        record = pb.collection("api_keys").get_one(key_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")
    if record.user != user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your key")
    pb.collection("api_keys").delete(key_id)
    return {"ok": True}


@router.get("/{key_id}/reveal")
async def reveal_key(key_id: str, user: dict = Depends(get_current_user)):
    try:
        record = pb.collection("api_keys").get_one(key_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")
    if record.user != user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your key")

    # Return the full key from storage (try both camelCase and snake_case)
    stored_key = getattr(record, "keyPlain", None) or getattr(record, "key_plain", None) or ""
    if not stored_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Full key not available (created before keyPlain storage)"
        )
    return {"key": stored_key}


@router.patch("/{key_id}")
async def update_key_limits(key_id: str, body: dict, user: dict = Depends(get_current_user)):
    try:
        record = pb.collection("api_keys").get_one(key_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")
    if record.user != user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your key")

    allowed = {"dailyRequests", "dailyTokens", "totalTokens"}
    update_data = {}
    field_map = {"dailyRequests": "daily_requests", "dailyTokens": "daily_tokens", "totalTokens": "total_tokens"}
    for k, v in body.items():
        if k in allowed and isinstance(v, (int, float)):
            update_data[field_map[k]] = int(v)

    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to update")

    pb.collection("api_keys").update(key_id, update_data)
    updated = pb.collection("api_keys").get_one(key_id)
    return _key_to_response(updated)


@router.post("/{key_id}/regenerate")
async def regenerate_key(key_id: str, user: dict = Depends(get_current_user)):
    try:
        record = pb.collection("api_keys").get_one(key_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")
    if record.user != user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your key")

    plain_key = _generate_api_key()
    key_hash = hashlib.sha256(plain_key.encode()).hexdigest()

    pb.collection("api_keys").update(key_id, {
        "keyHash": key_hash,
        "keyPrefix": plain_key[:12],
        "keyPlain": plain_key,
    })
    updated = pb.collection("api_keys").get_one(key_id)
    return _key_to_response(updated, plain_key)
