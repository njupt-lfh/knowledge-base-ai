"""消息/Chunk 反馈 — Phase 1.2"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base

FEEDBACK_TYPES = ("like", "dislike", "correction")


class ChunkFeedback(Base):
    __tablename__ = "chunk_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chunk_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    message_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kb_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    feedback_type: Mapped[str] = mapped_column(String(20), nullable=False)
    correction_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
