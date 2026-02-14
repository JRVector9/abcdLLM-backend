import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, status
from jose import jwt

from app.config import settings
from app.database import pb
from app.dependencies import get_current_user, _record_to_dict, API_KEY_PREFIX
from app.models.auth import LoginRequest, SignupRequest
from fastapi import Depends

router = APIRouter()


def _create_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _generate_api_key() -> str:
    return f"{API_KEY_PREFIX}{secrets.token_hex(24)}"


@router.post("/login")
async def login(body: LoginRequest, request: Request):
    try:
        result = pb.collection("users").auth_with_password(body.email, body.password)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    record = result.record
    # Update last active and IP
    try:
        client_ip = request.client.host if request.client else ""
        pb.collection("users").update(record.id, {
            "lastActive": datetime.now(timezone.utc).isoformat(),
            "lastIp": client_ip,
            "accessCount": (getattr(record, "access_count", 0) or 0) + 1,
        })
    except Exception:
        pass

    token = _create_token(record.id)
    return {"token": token, "user": _record_to_dict(record)}


@router.post("/signup")
async def signup(body: SignupRequest, request: Request):
    if body.password != body.passwordConfirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")

    api_key = _generate_api_key()
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    try:
        record = pb.collection("users").create({
            "email": body.email,
            "password": body.password,
            "passwordConfirm": body.passwordConfirm,
            "name": body.name,
            "role": "USER",
            "primaryApiKey": api_key[:12] + "..." ,
            "dailyUsage": 0,
            "dailyQuota": 5000,
            "totalUsage": 0,
            "totalQuota": 50000,
            "status": "active",
            "accessCount": 0,
            "lastActive": datetime.now(timezone.utc).isoformat(),
            "lastIp": request.client.host if request.client else "",
        })
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Create default API key record
    try:
        pb.collection("api_keys").create({
            "user": record.id,
            "name": "Default Key",
            "keyHash": key_hash,
            "keyPrefix": api_key[:12],
            "dailyRequests": 1000,
            "dailyTokens": 5000,
            "totalTokens": 50000,
            "usedRequests": 0,
            "usedTokens": 0,
            "totalUsedTokens": 0,
            "lastResetDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "isActive": True,
        })
    except Exception:
        pass

    token = _create_token(record.id)
    user_dict = _record_to_dict(record)
    user_dict["apiKey"] = api_key  # Return full key only on signup
    return {"token": token, "user": user_dict}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user
