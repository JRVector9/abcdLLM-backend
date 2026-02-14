"""
관리자 사용자 계정 생성 스크립트
"""

import json
import os
import urllib.request
import urllib.error
import ssl

PB_URL = os.environ.get("PB_URL", "https://abcdllm-db.jrai.space")
ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "jr@vector9.app")
ADMIN_PASSWORD = os.environ.get("PB_ADMIN_PASSWORD", "abcd1234567")

# 생성할 사용자 정보
USER_EMAIL = "jr@vector9.app"
USER_PASSWORD = "abcd1234567"
USER_NAME = "JR Admin"


def api(method: str, path: str, body: dict | None = None, token: str = "") -> dict:
    url = f"{PB_URL}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
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
    print("=== 관리자 사용자 생성 ===\n")

    # 1. Admin 인증
    print("[1/3] Admin 인증...")
    auth = api("POST", "/api/admins/auth-with-password", {
        "identity": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    token = auth["token"]
    print("  OK\n")

    # 2. users 컬렉션에 관리자 사용자 생성
    print("[2/3] 관리자 사용자 생성...")
    try:
        user = api("POST", "/api/collections/users/records", {
            "email": USER_EMAIL,
            "password": USER_PASSWORD,
            "passwordConfirm": USER_PASSWORD,
            "name": USER_NAME,
            "role": "ADMIN",
            "status": "active",
            "dailyQuota": 1000000,
            "totalQuota": 10000000,
            "dailyUsage": 0,
            "totalUsage": 0,
            "accessCount": 0,
        }, token)
        print(f"  OK - User ID: {user['id']}\n")
    except Exception as e:
        print(f"  Warning: {e}")
        print("  (이미 존재하는 경우 무시해도 됩니다)\n")

    # 3. API Key 생성
    print("[3/3] API Key 생성...")
    try:
        # 먼저 생성된 사용자 조회
        users = api("GET", f"/api/collections/users/records?filter=email='{USER_EMAIL}'", None, token)
        if users['items']:
            user_id = users['items'][0]['id']

            # API Key 생성 (sk-abcd- 형식)
            import hashlib
            import secrets
            plain_key = f"sk-abcd-{secrets.token_hex(24)}"
            key_hash = hashlib.sha256(plain_key.encode()).hexdigest()

            api_key = api("POST", "/api/collections/api_keys/records", {
                "user": user_id,
                "name": "Default API Key",
                "keyHash": key_hash,
                "keyPrefix": plain_key[:12],
                "keyPlain": plain_key,
                "dailyRequests": 10000,
                "dailyTokens": 1000000,
                "totalTokens": 10000000,
                "usedRequests": 0,
                "usedTokens": 0,
                "totalUsedTokens": 0,
                "isActive": True,
            }, token)

            # users 레코드에 primaryApiKey 업데이트
            api("PATCH", f"/api/collections/users/records/{user_id}", {
                "primaryApiKey": plain_key[:12] + "...",
            }, token)

            print(f"  OK\n")
            print("=" * 50)
            print(f"✅ 관리자 계정 생성 완료!")
            print("=" * 50)
            print(f"Email: {USER_EMAIL}")
            print(f"Password: {USER_PASSWORD}")
            print(f"Role: ADMIN")
            print(f"API Key: {plain_key}")
            print("=" * 50)
        else:
            print("  ERROR: 사용자를 찾을 수 없습니다.")
    except Exception as e:
        print(f"  Warning: {e}\n")


if __name__ == "__main__":
    main()
