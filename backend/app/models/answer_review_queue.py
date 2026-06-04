"""答案一致性审核队列 ORM 模型（Phase 2）。

记录双路径生成答案出现 CONFLICT / UNCERTAIN 时待人工审核的工单。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base

REVIEW_STATUSES = ("pending", "resolved", "dismissed")
REVIEW_VERDICTS = ("CONFLICT", "UNCERTAIN")


class AnswerReviewQueue(Base):
    """双路径答案一致性审核工单。"""

    __tablename__ = "answer_review_queue"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kb_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    answer_a: Mapped[str] = mapped_column(Text, nullable=False)
    answer_b: Mapped[str] = mapped_column(Text, nullable=False)
    ctx_hash: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    verdict: Mapped[str] = mapped_column(String(16), nullable=False, default="CONFLICT")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    route: Mapped[str | None] = mapped_column(String(32), nullable=True)
    gap_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    assignee: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
