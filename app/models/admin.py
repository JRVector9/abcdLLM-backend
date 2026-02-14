from pydantic import BaseModel
from typing import Optional


class SecurityEventResponse(BaseModel):
    id: str
    type: str
    severity: str
    description: str
    ip: str
    timestamp: str


class SystemMetricsResponse(BaseModel):
    cpu: float
    memory: float
    disk: float
    uptime: str
    activeRequests: int
    errorRate: float
    avgResponseTime: float


class ModelPerformanceResponse(BaseModel):
    name: str
    tokensPerSec: float
    avgLatency: float
    memoryUsage: str
    errorRate: float


class InsightsRequest(BaseModel):
    stats: dict
