"""入库冲突记录 — Phase 1.4"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base

CONFLICT_STATUSES = ("pending", "resolved_keep_new", "resolved_keep_old", "dismissed")


class KnowledgeConflict(Base):
    __tablename__ = "knowledge_conflicts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    knowledge_base_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    existing_chunk_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False
    )
    new_content: Mapped[str] = mapped_column(Text, nullable=False)
    similarity: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    llm_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_document_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    resolved_chunk_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
