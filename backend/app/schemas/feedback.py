from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    message_id: str
    feedback_type: str = Field(..., pattern="^(like|dislike|correction)$")
    chunk_id: str | None = None
    correction_text: str | None = None


class FeedbackResponse(BaseModel):
    id: str
    chunk_id: str | None
    message_id: str
    kb_id: str
    feedback_type: str
    correction_text: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
