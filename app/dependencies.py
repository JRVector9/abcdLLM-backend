import hashlib
from datetime import datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from app.config import settings
from app.database import pb

security = HTTPBearer()

API_KEY_PREFIX = "sk-abcd-"


def _decode_jwt(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """JWT-based auth for web dashboard endpoints."""
    token = credentials.credentials
    if token.startswith(API_KEY_PREFIX):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Use JWT token for this endpoint")
    payload = _decode_jwt(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    try:
        record = pb.collection("users").get_one(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return _record_to_dict(record)


async def get_api_key_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """API Key or JWT auth for Ollama proxy endpoints."""
    token = credentials.credentials

    if token.startswith(API_KEY_PREFIX):
        key_hash = hashlib.sha256(token.encode()).hexdigest()
        try:
            results = pb.collection("api_keys").get_list(1, 1, {"filter": f'keyHash="{key_hash}" && isActive=true'})
            if not results.items:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
            key_record = results.items[0]
            user_record = pb.collection("users").get_one(key_record.user)
            if user_record.status == "blocked":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account blocked")
            return {**_record_to_dict(user_record), "_api_key_id": key_record.id}
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    else:
        return await get_current_user(credentials)


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def _record_to_dict(record) -> dict:
    last_active = getattr(record, "last_active", "") or ""
    if hasattr(last_active, "isoformat"):
        last_active = last_active.isoformat()
    return {
        "id": record.id,
        "email": getattr(record, "email", ""),
        "name": getattr(record, "name", ""),
        "role": getattr(record, "role", "USER"),
        "apiKey": getattr(record, "primary_api_key", ""),
        "usage": getattr(record, "total_usage", 0) or 0,
        "dailyUsage": getattr(record, "daily_usage", 0) or 0,
        "dailyQuota": getattr(record, "daily_quota", 5000) or 5000,
        "totalQuota": getattr(record, "total_quota", 50000) or 50000,
        "lastActive": str(last_active),
        "ip": getattr(record, "last_ip", "") or "",
        "status": getattr(record, "status", "active"),
        "accessCount": getattr(record, "access_count", 0) or 0,
    }
