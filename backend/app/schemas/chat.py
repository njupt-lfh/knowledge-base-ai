"""对话 Schema"""

from datetime import datetime
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    knowledge_base_id: str = Field(...)


class ConversationResponse(BaseModel):
    id: str
    knowledge_base_id: str
    title: str
    share_token: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    sources: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ShareResponse(BaseModel):
    share_token: str
    share_url: str
