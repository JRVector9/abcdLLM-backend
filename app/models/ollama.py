from pydantic import BaseModel
from typing import Optional


class MessageSchema(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: Optional[str] = None
    messages: list[MessageSchema]
    stream: bool = False
    options: Optional[dict] = None
    think: Optional[bool] = None  # None = 모델 기본값, False = thinking 비활성화(빠름)


class ChatResponse(BaseModel):
    model: str
    message: MessageSchema
    done: bool = True
    total_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    eval_count: Optional[int] = None


class ModelShowRequest(BaseModel):
    name: str


class ModelInfo(BaseModel):
    name: str
    size: str
    modified: str
    parameterCount: Optional[str] = None
