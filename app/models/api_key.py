from pydantic import BaseModel
from typing import Optional


class ApiKeyCreateRequest(BaseModel):
    name: str
    dailyRequests: int = 1000
    dailyTokens: int = 5000
    totalTokens: int = 50000


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key: str
    createdAt: str
    dailyRequests: int
    dailyTokens: int
    totalTokens: int
