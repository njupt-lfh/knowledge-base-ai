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

# 补全任务队列视图（前端 Tab）
GAP_PENDING_STATUSES = ("pending", "suggested", "processing", "manual_required")
GAP_COMPLETED_STATUSES = ("approved", "rejected")

GAP_AUDIT_ACTIONS = (
    "created",
    "status_changed",
    "ingest_started",
    "ingest_completed",
    "ingest_failed",
    "deleted",
    "follow_up_created",
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
    document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    parent_gap_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GapAuditLog(Base):
    """Gap 处理记录（状态变更、入库等）。"""

    __tablename__ = "gap_audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kb_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    gap_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
