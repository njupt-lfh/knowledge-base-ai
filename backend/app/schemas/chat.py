"""对话 Schema"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


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


class SourceItem(BaseModel):
    chunk_id: str
    content: str
    score: float
    chunk_index: int | None = None
    document_id: str | None = None


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    sources: list[SourceItem] | None = None
    created_at: datetime

    @field_validator("sources", mode="before")
    @classmethod
    def normalize_sources(cls, v):
        if v is None:
            return None
        if isinstance(v, list):
            return v
        return None

    model_config = {"from_attributes": True}


class ShareResponse(BaseModel):
    share_token: str
    share_url: str
