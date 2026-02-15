"""
usage_logs 콜렉션 생성 스크립트
"""

import json
import os
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
        print(f"ERROR {e.code}: {err_body}")
        raise


def main():
    print("=== usage_logs 콜렉션 생성 ===\n")

    # 1. Admin 인증
    print("[1/3] Admin 인증...")
    auth = api("POST", "/api/admins/auth-with-password", {
        "identity": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    token = auth["token"]
    print("  OK\n")

    # 2. 기존 콜렉션 목록 가져오기
    print("[2/3] 기존 콜렉션 조회...")
    result = api("GET", "/api/collections", token=token)

    # 응답 구조 확인
    if isinstance(result, dict):
        collections = result.get("items", [])
    else:
        collections = result

    # api_keys 콜렉션 ID 찾기
    api_keys_id = None
    for col in collections:
        if col["name"] == "api_keys":
            api_keys_id = col["id"]
            print(f"  api_keys collection ID: {api_keys_id}")
            break

    if not api_keys_id:
        print("  ERROR: api_keys 콜렉션을 찾을 수 없습니다!")
        return
    print("  OK\n")

    # 3. usage_logs 콜렉션 생성
    print("[3/3] usage_logs 콜렉션 생성...")
    try:
        result = api("POST", "/api/collections", {
            "name": "usage_logs",
            "type": "base",
            "schema": [
                {"name": "user", "type": "relation", "options": {"collectionId": "_pb_users_auth_", "maxSelect": 1}},
                {"name": "apiKey", "type": "relation", "options": {"collectionId": api_keys_id, "maxSelect": 1}},
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
        print("=== 완료! ===")
        print(f"usage_logs 콜렉션이 생성되었습니다.")
        print(f"Collection ID: {result['id']}")
    except Exception as e:
        print(f"  ERROR: {e}\n")


if __name__ == "__main__":
    main()
