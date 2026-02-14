from pydantic import BaseModel
from typing import Optional


class ApplicationCreateRequest(BaseModel):
    projectName: str
    useCase: str
    requestedQuota: int
    targetModel: Optional[str] = None


class ApplicationUpdateRequest(BaseModel):
    status: str  # approved / rejected
    adminNote: Optional[str] = None
