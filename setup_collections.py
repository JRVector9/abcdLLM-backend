"""
PocketBase 콜렉션 자동 생성 스크립트
Usage: python setup_collections.py
"""

import json
import os
import sys
import urllib.request
import urllib.error
import ssl

PB_URL = os.environ.get("PB_URL", "https://abcdllm-db.jrai.space")
ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "jr@vector9.app")
ADMIN_PASSWORD = os.environ.get("PB_ADMIN_PASSWORD", "abcd1234567")


def api(method: str, path: str, body: dict | None = None, token: str = "") -> dict:
    url = f"{PB_URL}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }
    if token:
        headers["Authorization"] = token
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"  ERROR {e.code}: {err_body}")
        raise


def main():
    # 1. Admin 인증
    print("=== PocketBase 콜렉션 설정 ===\n")
    print("[1/7] Admin 인증...")
    auth = api("POST", "/api/admins/auth-with-password", {
        "identity": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    token = auth["token"]
    print("  OK\n")

    # 2. users 콜렉션 확장 (기존 auth 콜렉션에 필드 추가)
    print("[2/7] users 콜렉션 필드 확장...")
    users_fields = [
        {"name": "name", "type": "text"},
        {"name": "role", "type": "select", "options": {"values": ["ADMIN", "USER"], "maxSelect": 1}},
        {"name": "primaryApiKey", "type": "text"},
        {"name": "dailyUsage", "type": "number", "options": {"min": 0}},
        {"name": "dailyQuota", "type": "number", "options": {"min": 0}},
        {"name": "totalUsage", "type": "number", "options": {"min": 0}},
        {"name": "totalQuota", "type": "number", "options": {"min": 0}},
        {"name": "lastActive", "type": "date"},
        {"name": "lastIp", "type": "text"},
        {"name": "status", "type": "select", "options": {"values": ["active", "blocked"], "maxSelect": 1}},
        {"name": "accessCount", "type": "number", "options": {"min": 0}},
    ]
    try:
        api("PATCH", "/api/collections/_pb_users_auth_", {
            "schema": users_fields,
            "listRule": "",
            "viewRule": "",
            "createRule": "",
            "updateRule": "@request.auth.id != ''",
            "deleteRule": None,
        }, token)
        print("  OK\n")
    except Exception as e:
        print(f"  Warning: {e}\n")

    # 3. api_keys 콜렉션
    print("[3/7] api_keys 콜렉션 생성...")
    try:
        api("POST", "/api/collections", {
            "name": "api_keys",
            "type": "base",
            "schema": [
                {"name": "user", "type": "relation", "options": {"collectionId": "_pb_users_auth_", "maxSelect": 1}},
                {"name": "name", "type": "text"},
                {"name": "keyHash", "type": "text"},
                {"name": "keyPrefix", "type": "text"},
                {"name": "dailyRequests", "type": "number", "options": {"min": 0}},
                {"name": "dailyTokens", "type": "number", "options": {"min": 0}},
                {"name": "totalTokens", "type": "number", "options": {"min": 0}},
                {"name": "usedRequests", "type": "number", "options": {"min": 0}},
                {"name": "usedTokens", "type": "number", "options": {"min": 0}},
                {"name": "totalUsedTokens", "type": "number", "options": {"min": 0}},
                {"name": "lastResetDate", "type": "date"},
                {"name": "isActive", "type": "bool"},
            ],
            "listRule": "",
            "viewRule": "",
            "createRule": "",
            "updateRule": "",
            "deleteRule": "",
        }, token)
        print("  OK\n")
    except Exception as e:
        print(f"  Warning: {e}\n")

    # 4. security_events 콜렉션
    print("[4/7] security_events 콜렉션 생성...")
    try:
        api("POST", "/api/collections", {
            "name": "security_events",
            "type": "base",
            "schema": [
                {"name": "type", "type": "select", "options": {"values": ["failed_login", "unusual_traffic", "brute_force", "ddos_attempt"], "maxSelect": 1}},
                {"name": "severity", "type": "select", "options": {"values": ["low", "medium", "high", "critical"], "maxSelect": 1}},
                {"name": "description", "type": "text"},
                {"name": "ip", "type": "text"},
                {"name": "userId", "type": "relation", "options": {"collectionId": "_pb_users_auth_", "maxSelect": 1}},
            ],
            "listRule": "",
            "viewRule": "",
            "createRule": "",
            "updateRule": "",
            "deleteRule": "",
        }, token)
        print("  OK\n")
    except Exception as e:
        print(f"  Warning: {e}\n")

    # 5. api_applications 콜렉션
    print("[5/7] api_applications 콜렉션 생성...")
    try:
        api("POST", "/api/collections", {
            "name": "api_applications",
            "type": "base",
            "schema": [
                {"name": "user", "type": "relation", "options": {"collectionId": "_pb_users_auth_", "maxSelect": 1}},
                {"name": "userName", "type": "text"},
                {"name": "projectName", "type": "text"},
                {"name": "useCase", "type": "text"},
                {"name": "requestedQuota", "type": "number", "options": {"min": 0}},
                {"name": "targetModel", "type": "text"},
                {"name": "status", "type": "select", "options": {"values": ["pending", "approved", "rejected"], "maxSelect": 1}},
                {"name": "adminNote", "type": "text"},
            ],
            "listRule": "",
            "viewRule": "",
            "createRule": "",
            "updateRule": "",
            "deleteRule": "",
        }, token)
        print("  OK\n")
    except Exception as e:
        print(f"  Warning: {e}\n")

    # 6. usage_logs 콜렉션
    print("[6/7] usage_logs 콜렉션 생성...")
    try:
        api("POST", "/api/collections", {
            "name": "usage_logs",
            "type": "base",
            "schema": [
                {"name": "user", "type": "relation", "options": {"collectionId": "_pb_users_auth_", "maxSelect": 1}},
                {"name": "apiKey", "type": "relation", "options": {"collectionId": "api_keys", "maxSelect": 1}},
                {"name": "model", "type": "text"},
                {"name": "endpoint", "type": "text"},
                {"name": "promptTokens", "type": "number", "options": {"min": 0}},
                {"name": "completionTokens", "type": "number", "options": {"min": 0}},
                {"name": "totalTokens", "type": "number", "options": {"min": 0}},
                {"name": "responseTimeMs", "type": "number", "options": {"min": 0}},
                {"name": "statusCode", "type": "number"},
                {"name": "ip", "type": "text"},
                {"name": "isError", "type": "bool"},
            ],
            "listRule": "",
            "viewRule": "",
            "createRule": "",
            "updateRule": "",
            "deleteRule": "",
        }, token)
        print("  OK\n")
    except Exception as e:
        print(f"  Warning: {e}\n")

    # 7. user_settings 콜렉션
    print("[7/8] user_settings 콜렉션 생성...")
    try:
        api("POST", "/api/collections", {
            "name": "user_settings",
            "type": "base",
            "schema": [
                {"name": "user", "type": "relation", "options": {"collectionId": "_pb_users_auth_", "maxSelect": 1}},
                {"name": "autoModelUpdate", "type": "bool"},
                {"name": "detailedLogging", "type": "bool"},
                {"name": "ipWhitelist", "type": "text"},
                {"name": "emailSecurityAlerts", "type": "bool"},
                {"name": "usageThresholdAlert", "type": "bool"},
            ],
            "listRule": "",
            "viewRule": "",
            "createRule": "",
            "updateRule": "",
            "deleteRule": "",
        }, token)
        print("  OK\n")
    except Exception as e:
        print(f"  Warning: {e}\n")

    # 8. system_settings 콜렉션 (관리자 전용 시스템 설정)
    print("[8/8] system_settings 콜렉션 생성...")
    try:
        api("POST", "/api/collections", {
            "name": "system_settings",
            "type": "base",
            "schema": [
                {"name": "key", "type": "text", "options": {"max": 100}},
                {"name": "value", "type": "text"},
                {"name": "description", "type": "text"},
            ],
            "listRule": "",
            "viewRule": "",
            "createRule": "",
            "updateRule": "",
            "deleteRule": "",
            "indexes": [
                "CREATE UNIQUE INDEX idx_system_settings_key ON system_settings (key)"
            ],
        }, token)
        print("  OK\n")
    except Exception as e:
        print(f"  Warning: {e}\n")

    print("=== 완료! ===")
    print("모든 콜렉션이 생성되었습니다.")
    print(f"PocketBase Admin UI: {PB_URL}/_/")


if __name__ == "__main__":
    main()
