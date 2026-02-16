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
