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
    stored_key = getattr(record, "keyPlain", None) or ""
    return {
        "id": record.id,
        "name": getattr(record, "name", ""),
        "key": plain_key or stored_key or (getattr(record, "keyPrefix", "") + "..."),
        "createdAt": str(created),
        "dailyRequests": getattr(record, "dailyRequests", 0) or 0,
        "dailyTokens": getattr(record, "dailyTokens", 0) or 0,
        "totalTokens": getattr(record, "totalTokens", 0) or 0,
    }


@router.get("")
async def list_keys(user: dict = Depends(get_current_user)):
    results = pb.collection("api_keys").get_list(1, 50, {"filter": f'user="{user["id"]}"'})
    return [_key_to_response(r) for r in results.items]


@router.post("")
async def create_key(body: ApiKeyCreateRequest, user: dict = Depends(get_current_user)):
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
