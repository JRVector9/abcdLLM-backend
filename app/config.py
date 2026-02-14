from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    POCKETBASE_URL: str = "http://127.0.0.1:8090"
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"

    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
