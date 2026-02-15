from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, user, keys, ollama_proxy, applications, admin, settings as settings_router
from app.middleware.error_handler import register_error_handlers
from app.middleware.request_logger import RequestLoggerMiddleware
from app.middleware.rate_limiter import setup_rate_limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작 및 종료 시 실행되는 로직"""
    # Startup: Ollama 자동 감지 및 구성
    from app.services.ollama_detector import auto_configure_ollama
    await auto_configure_ollama()

    yield

    # Shutdown: 필요한 경우 정리 작업


app = FastAPI(title="abcdLLM API", version="1.0.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware
app.add_middleware(RequestLoggerMiddleware)
register_error_handlers(app)
setup_rate_limiter(app)

# Routers
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(user.router, prefix="/api/user", tags=["User"])
app.include_router(keys.router, prefix="/api/keys", tags=["API Keys"])
app.include_router(ollama_proxy.router, prefix="/api/v1", tags=["Ollama Proxy"])
app.include_router(ollama_proxy.openai_router, prefix="/v1", tags=["OpenAI Compatible"])
app.include_router(ollama_proxy.ollama_native_router, prefix="/api", tags=["Ollama Native"])
app.include_router(applications.router, prefix="/api/applications", tags=["Applications"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["Settings"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
