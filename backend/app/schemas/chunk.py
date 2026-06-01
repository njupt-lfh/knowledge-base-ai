"""知识块 API 请求/响应 Schema。

定义 chunk 编辑、检索测试的请求/响应模型，
由 `api/chunk.py` 与 `ChunkService` 使用。
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ChunkUpdate(BaseModel):
    """更新知识块请求体（内容或启用状态）。"""

    content: str | None = None
    is_active: bool | None = None


class ChunkResponse(BaseModel):
    """知识块详情响应。"""

    id: str
    document_id: str
    knowledge_base_id: str
    content: str
    chunk_index: int
    char_count: int
    is_active: bool
    hit_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchRequest(BaseModel):
    """知识库内检索测试请求体。"""

    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResultItem(BaseModel):
    """单条检索结果。"""

    chunk_id: str
    content: str
    score: float
    document_id: str
    chunk_index: int


class SearchResponse(BaseModel):
    """检索测试响应。"""

    items: list[SearchResultItem]
    query: str
