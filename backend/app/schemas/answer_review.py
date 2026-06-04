"""答案审核队列 API Schema。"""

from datetime import datetime

from pydantic import BaseModel, Field


class AnswerReviewResponse(BaseModel):
    """审核队列条目响应。"""

    id: str
    kb_id: str
    query: str
    answer_a: str
    answer_b: str
    ctx_hash: str
    verdict: str
    reason: str | None
    route: str | None
    gap_id: str | None
    status: str
    assignee: str | None
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class AnswerReviewCreateRequest(BaseModel):
    """手动入队（测试/管理用）。"""

    query: str
    answer_a: str
    answer_b: str
    verdict: str = Field(default="CONFLICT", description="CONFLICT|UNCERTAIN")
    reason: str | None = None
    route: str | None = None
    ctx_hash: str = ""


class AnswerReviewStatusUpdate(BaseModel):
    """更新审核状态。"""

    status: str = Field(..., description="pending|resolved|dismissed")
    assignee: str | None = None
