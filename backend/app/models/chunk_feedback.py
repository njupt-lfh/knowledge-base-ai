"""消息/Chunk 反馈 ORM 模型（Phase 1.2）。

定义 `ChunkFeedback` 表及 `FEEDBACK_TYPES` 常量，记录用户对助手回复或
具体 chunk 的点赞、点踩与纠错文本，驱动质量分重算。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base

FEEDBACK_TYPES = ("like", "dislike", "correction")


class ChunkFeedback(Base):
    """单条用户反馈记录。

    关键字段：message_id 关联对话消息；chunk_id 可选（整句反馈时为空）；
    feedback_type 限定为 like/dislike/correction；correction_text 存纠错内容。
    """

    __tablename__ = "chunk_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chunk_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    message_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kb_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    feedback_type: Mapped[str] = mapped_column(String(20), nullable=False)
    correction_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
