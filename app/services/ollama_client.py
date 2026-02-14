import httpx

from app.config import settings

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(base_url=settings.OLLAMA_BASE_URL, timeout=120.0)
    return _client


async def chat(payload: dict) -> dict:
    client = get_client()
    resp = await client.post("/api/chat", json=payload)
    resp.raise_for_status()
    return resp.json()


async def list_models() -> dict:
    client = get_client()
    resp = await client.get("/api/tags")
    resp.raise_for_status()
    return resp.json()


async def generate(payload: dict) -> dict:
    client = get_client()
    resp = await client.post("/api/generate", json=payload)
    resp.raise_for_status()
    return resp.json()


async def show_model(name: str) -> dict:
    client = get_client()
    resp = await client.post("/api/show", json={"name": name})
    resp.raise_for_status()
    return resp.json()


async def health_check() -> bool:
    try:
        client = get_client()
        resp = await client.get("/", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False
