"""对话 API 请求/响应 Schema。

定义聊天、会话列表、消息与分享链接的 Pydantic 模型，
由 `api/chat.py` 与 `ChatService` 使用。
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """发送聊天消息请求体。"""

    message: str = Field(..., min_length=1)
    knowledge_base_id: str = Field(...)


class ConversationResponse(BaseModel):
    """对话会话响应。"""

    id: str
    knowledge_base_id: str
    title: str
    share_token: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceItem(BaseModel):
    """RAG 引用来源项。"""

    chunk_id: str
    content: str
    score: float
    chunk_index: int | None = None
    document_id: str | None = None


class MessageResponse(BaseModel):
    """单条消息响应。"""

    id: str
    conversation_id: str
    role: str
    content: str
    sources: list[SourceItem] | None = None
    created_at: datetime

    @field_validator("sources", mode="before")
    @classmethod
    def normalize_sources(cls, v):
        """将 ORM 中 JSON 或非列表的 sources 规范化为 SourceItem 列表或 None。"""
        if v is None:
            return None
        if isinstance(v, list):
            return v
        return None

    model_config = {"from_attributes": True}


class ShareResponse(BaseModel):
    """生成分享链接响应。"""

    share_token: str
    share_url: str
