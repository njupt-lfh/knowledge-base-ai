"""文档 API 请求/响应 Schema。

定义手工文档创建、单文档与分页列表的 Pydantic 模型，
供 `api/document.py` 与文档服务层序列化使用。
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ManualDocumentCreate(BaseModel):
    """手工录入文档请求体。"""

    title: str = Field(..., max_length=512)
    content: str = Field(..., min_length=1)


class DocumentResponse(BaseModel):
    """文档详情响应。"""

    id: str
    knowledge_base_id: str
    filename: str
    file_type: str
    file_path: str | None
    file_size: int | None
    status: str
    chunk_count: int
    char_count: int
    ingest_duplicate_count: int = 0
    ingest_conflict_count: int = 0
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """分页文档列表响应。"""

    items: list[DocumentResponse]
    total: int
