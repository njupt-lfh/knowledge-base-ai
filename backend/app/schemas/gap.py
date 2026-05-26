"""知识缺口 API Schema"""

from datetime import datetime

from pydantic import BaseModel, Field


class GapResponse(BaseModel):
    id: str
    kb_id: str
    query: str
    conversation_id: str | None
    message_id: str | None
    gap_type: str
    status: str
    suggested_content: str | None
    source_ref: str | None
    confidence: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class GapStatusUpdate(BaseModel):
    status: str = Field(..., description="pending|suggested|approved|rejected|manual_required")


class GapCreateRequest(BaseModel):
    query: str
    gap_type: str | None = None
    source_ref: str | None = None
    correction_text: str | None = None


class GapIngestRequest(BaseModel):
    manual_content: str | None = Field(None, description="KNOWLEDGE_ABSENT 必填；其他类型可覆盖建议内容")
    manual_title: str | None = None
