"""知识库 API 请求/响应 Schema。

定义知识库 CRUD 的 Pydantic 模型：创建/更新入参校验、列表与详情响应结构，
由 `api/knowledge.py` 与 `KnowledgeService` 使用。
"""

from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    """创建知识库请求体。"""

    name: str = Field(..., max_length=255)
    description: str | None = None
    chunk_size: int = Field(default=500, ge=100, le=2000)
    chunk_overlap: int = Field(default=50, ge=0, le=500)


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库请求体（字段均可选）。"""

    name: str | None = Field(None, max_length=255)
    description: str | None = None
    chunk_size: int | None = Field(None, ge=100, le=2000)
    chunk_overlap: int | None = Field(None, ge=0, le=500)


class KnowledgeBaseResponse(BaseModel):
    """知识库详情/列表项响应。"""

    id: str
    name: str
    description: str | None
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    created_at: datetime
    updated_at: datetime
    document_count: int = 0
    total_hits: int = 0

    model_config = {"from_attributes": True}


class KnowledgeBaseListResponse(BaseModel):
    """分页知识库列表响应。"""

    items: list[KnowledgeBaseResponse]
    total: int
