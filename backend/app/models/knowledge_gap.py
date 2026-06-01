"""知识缺口队列 ORM 模型（Phase 1）。

定义 `KnowledgeGap` 表及缺口类型/状态常量，跟踪检索未命中、用户补充、
纠错等待入库等场景，供缺口治理与自动分类流程使用。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base

GAP_TYPES = (
    "RETRIEVAL_MISS",
    "USER_PROVIDED",
    "USER_CORRECTION",
    "KNOWLEDGE_ABSENT",
)

GAP_STATUSES = (
    "pending",
    "suggested",
    "processing",
    "approved",
    "rejected",
    "manual_required",
)


class KnowledgeGap(Base):
    """知识缺口工单实体。

    关键字段：query 触发问题；gap_type/status 驱动工作流；suggested_content
    与 source_ref 支持半自动入库；confidence 可选置信度。
    """

    __tablename__ = "knowledge_gaps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kb_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    gap_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    suggested_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
