"""文档 Schema"""

from datetime import datetime

from pydantic import BaseModel, Field


class ManualDocumentCreate(BaseModel):
    title: str = Field(..., max_length=512)
    content: str = Field(..., min_length=1)


class DocumentResponse(BaseModel):
    id: str
    knowledge_base_id: str
    filename: str
    file_type: str
    file_path: str | None
    file_size: int | None
    status: str
    chunk_count: int
    char_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
