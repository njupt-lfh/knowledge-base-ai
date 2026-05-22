"""知识块 Schema"""

from datetime import datetime
from pydantic import BaseModel, Field


class ChunkUpdate(BaseModel):
    content: str | None = None
    is_active: bool | None = None


class ChunkResponse(BaseModel):
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
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResultItem(BaseModel):
    chunk_id: str
    content: str
    score: float
    document_id: str
    chunk_index: int


class SearchResponse(BaseModel):
    items: list[SearchResultItem]
    query: str
