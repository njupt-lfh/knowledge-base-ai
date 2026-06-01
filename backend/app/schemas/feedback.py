"""用户反馈 API 请求/响应 Schema。

定义点赞/点踩/纠错提交的入参与持久化后的反馈记录响应，
由 `api/feedback.py` 与 `FeedbackService` 使用。
"""

from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    """提交反馈请求体。"""

    message_id: str
    feedback_type: str = Field(..., pattern="^(like|dislike|correction)$")
    chunk_id: str | None = None
    chunk_ids: list[str] | None = None
    correction_text: str | None = None


class FeedbackResponse(BaseModel):
    """反馈记录响应。"""

    id: str
    chunk_id: str | None
    message_id: str
    kb_id: str
    feedback_type: str
    correction_text: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
