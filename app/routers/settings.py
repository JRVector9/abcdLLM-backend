import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.database import pb
from app.dependencies import get_current_user, API_KEY_PREFIX
from app.models.settings import UserSettingsUpdateRequest, WhitelistUpdateRequest

router = APIRouter()


def _get_or_create_settings(user_id: str) -> object:
    try:
        results = pb.collection("user_settings").get_list(1, 1, {"filter": f'user="{user_id}"'})
        if results.items:
            return results.items[0]
    except Exception:
        pass
    return pb.collection("user_settings").create({
        "user": user_id,
        "autoModelUpdate": False,
        "detailedLogging": False,
        "ipWhitelist": "",
        "emailSecurityAlerts": False,
        "usageThresholdAlert": False,
    })


def _settings_to_response(record) -> dict:
    return {
        "autoModelUpdate": getattr(record, "auto_model_update", False),
        "detailedLogging": getattr(record, "detailed_logging", False),
        "ipWhitelist": getattr(record, "ip_whitelist", ""),
        "emailSecurityAlerts": getattr(record, "email_security_alerts", False),
        "usageThresholdAlert": getattr(record, "usage_threshold_alert", False),
    }


@router.get("")
async def get_settings(user: dict = Depends(get_current_user)):
    record = _get_or_create_settings(user["id"])
    # Include user info for settings page
    return {
        **_settings_to_response(record),
        "user": user,
    }


@router.patch("")
async def update_settings(body: UserSettingsUpdateRequest, user: dict = Depends(get_current_user)):
    record = _get_or_create_settings(user["id"])
    update_data = body.model_dump(exclude_none=True)
    if update_data:
        pb.collection("user_settings").update(record.id, update_data)
    updated = _get_or_create_settings(user["id"])
    return _settings_to_response(updated)


@router.post("/api-key/refresh")
async def refresh_api_key(user: dict = Depends(get_current_user)):
    plain_key = f"{API_KEY_PREFIX}{secrets.token_hex(24)}"
    key_hash = hashlib.sha256(plain_key.encode()).hexdigest()

    # Find user's default key and regenerate
    try:
        results = pb.collection("api_keys").get_list(
            1, 1, {"filter": f'user="{user["id"]}"', "sort": "created"}
        )
        if results.items:
            key_record = results.items[0]
            pb.collection("api_keys").update(key_record.id, {
                "keyHash": key_hash,
                "keyPrefix": plain_key[:12],
            })
    except Exception:
        pass

    pb.collection("users").update(user["id"], {
        "primaryApiKey": plain_key[:12] + "...",
    })

    return {"apiKey": plain_key}


@router.patch("/whitelist")
async def update_whitelist(body: WhitelistUpdateRequest, user: dict = Depends(get_current_user)):
    record = _get_or_create_settings(user["id"])
    pb.collection("user_settings").update(record.id, {"ipWhitelist": body.ipWhitelist})
    return {"ipWhitelist": body.ipWhitelist}
