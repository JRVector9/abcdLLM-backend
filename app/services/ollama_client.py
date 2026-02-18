import httpx

from app.config import settings

_client: httpx.AsyncClient | None = None


def _get_ollama_base_url() -> str:
    """DB에서 Ollama URL을 가져옵니다. Redis 캐시 우선, 없으면 config 기본값 사용"""
    from app.services import cache

    cached = cache.get_cached_ollama_url()
    if cached:
        return cached

    try:
        from app.database import pb
        results = pb.collection("system_settings").get_list(1, 1, {"filter": 'key="ollama_base_url"'})
        if results.items:
            url = getattr(results.items[0], "value", settings.OLLAMA_BASE_URL)
            cache.set_cached_ollama_url(url)
            return url
    except Exception:
        pass
    return settings.OLLAMA_BASE_URL


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        base_url = _get_ollama_base_url()
        _client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(connect=5.0, read=300.0, write=30.0, pool=10.0),
        )
    return _client


def reset_client() -> None:
    """클라이언트를 재설정합니다 (URL 변경 시 사용)"""
    global _client
    if _client is not None and not _client.is_closed:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(_client.aclose())
            else:
                asyncio.run(_client.aclose())
        except Exception:
            pass
    _client = None


async def chat(payload: dict) -> dict:
    if "keep_alive" not in payload:
        payload["keep_alive"] = settings.OLLAMA_KEEP_ALIVE
    client = get_client()
    resp = await client.post("/api/chat", json=payload)
    resp.raise_for_status()
    return resp.json()


async def chat_stream(payload: dict):
    """Ollama /api/chat를 NDJSON 스트리밍으로 반환하는 async generator.
    기존 persistent client를 재사용해 TCP 연결 오버헤드 제거."""
    if "keep_alive" not in payload:
        payload["keep_alive"] = settings.OLLAMA_KEEP_ALIVE
    client = get_client()  # persistent client 재사용
    async with client.stream("POST", "/api/chat", json=payload) as resp:
        resp.raise_for_status()
        async for chunk in resp.aiter_bytes():
            if chunk:
                yield chunk


async def warmup(model: str | None = None) -> None:
    """서버 시작 시 기본 모델을 VRAM에 미리 로드. 첫 요청 콜드 스타트 제거."""
    target = model or settings.DEFAULT_MODEL
    try:
        client = get_client()
        await client.post("/api/chat", json={
            "model": target,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
            "think": False,
            "keep_alive": settings.OLLAMA_KEEP_ALIVE,
        })
    except Exception:
        pass  # 워밍 실패해도 서버 시작은 계속


async def list_models() -> dict:
    client = get_client()
    resp = await client.get("/api/tags")
    resp.raise_for_status()
    return resp.json()


async def generate(payload: dict) -> dict:
    if "keep_alive" not in payload:
        payload["keep_alive"] = settings.OLLAMA_KEEP_ALIVE
    client = get_client()
    resp = await client.post("/api/generate", json=payload)
    resp.raise_for_status()
    return resp.json()


async def show_model(name: str) -> dict:
    client = get_client()
    resp = await client.post("/api/show", json={"name": name})
    resp.raise_for_status()
    return resp.json()


async def pull_model(name: str) -> dict:
    client = get_client()
    # stream=false returns once when pull is completed
    resp = await client.post("/api/pull", json={"name": name, "stream": False})
    resp.raise_for_status()
    return resp.json()


async def health_check() -> bool:
    try:
        client = get_client()
        resp = await client.get("/", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False
