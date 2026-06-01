"""知识缺口 API 请求/响应 Schema。

定义缺口列表、创建、状态更新与批准入库的 Pydantic 模型，
由 `api/gap.py` 与 `GapService` 使用。
"""

from datetime import datetime

from pydantic import BaseModel, Field


class GapResponse(BaseModel):
    """知识缺口工单响应。"""

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
    """更新缺口状态请求体。"""

    status: str = Field(..., description="pending|suggested|approved|rejected|manual_required")


class GapCreateRequest(BaseModel):
    """手动创建缺口请求体。"""

    query: str
    gap_type: str | None = None
    source_ref: str | None = None
    correction_text: str | None = None


class GapIngestRequest(BaseModel):
    """批准缺口入库请求体。"""

    manual_content: str | None = Field(
        None, description="KNOWLEDGE_ABSENT 必填；其他类型可覆盖建议内容"
    )
    manual_title: str | None = None
