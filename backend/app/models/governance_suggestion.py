"""治理建议与审计日志 ORM 模型（Phase 3 治理闭环）。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base

SUGGESTION_TYPES = (
    "duplicate",
    "cold_stale",
    "high_quality_zero_hit",
    "low_quality",
    "archive_candidate",
)

SUGGESTION_STATUSES = ("pending", "approved", "dismissed", "executed", "verified")


class GovernanceSuggestion(Base):
    """持久化治理建议工单。"""

    __tablename__ = "governance_suggestions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kb_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    suggestion_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    chunk_ids: Mapped[str] = mapped_column(Text, nullable=False)  # JSON list
    recommended_action: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="warning")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    executed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scan_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    content_preview: Mapped[str | None] = mapped_column(Text, nullable=True)


class GovernanceAuditLog(Base):
    """治理操作审计日志。"""

    __tablename__ = "governance_audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kb_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    suggestion_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # approve/dismiss/execute/verify
    operator: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chunk_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
