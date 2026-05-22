"""知识库 Schema"""

from datetime import datetime
from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    chunk_size: int = Field(default=500, ge=100, le=2000)
    chunk_overlap: int = Field(default=50, ge=0, le=500)


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    chunk_size: int | None = Field(None, ge=100, le=2000)
    chunk_overlap: int | None = Field(None, ge=0, le=500)


class KnowledgeBaseResponse(BaseModel):
    id: str
    name: str
    description: str | None
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    created_at: datetime
    updated_at: datetime
    document_count: int = 0

    model_config = {"from_attributes": True}


class KnowledgeBaseListResponse(BaseModel):
    items: list[KnowledgeBaseResponse]
    total: int
