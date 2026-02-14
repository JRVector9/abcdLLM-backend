from pydantic import BaseModel
from typing import Optional


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    apiKey: str
    usage: int
    dailyUsage: int
    dailyQuota: int
    totalQuota: int
    lastActive: str
    ip: str
    status: str
    accessCount: int


class DashboardResponse(BaseModel):
    user: UserResponse
    recentUsage: list[dict]
    activeModels: int
    totalRequests: int


class QuotaResponse(BaseModel):
    dailyUsage: int
    dailyQuota: int
    totalUsage: int
    totalQuota: int
    resetTime: str


class UserUpdateRequest(BaseModel):
    status: Optional[str] = None
    dailyQuota: Optional[int] = None
    totalQuota: Optional[int] = None
    role: Optional[str] = None
