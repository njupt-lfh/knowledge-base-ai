"""Chunk 质量分 ORM 模型（Phase 1.2）。

定义 `ChunkQuality` 表，聚合用户反馈驱动的质量评分与审核标记，
供治理与低质量 chunk 列表 API 使用。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class ChunkQuality(Base):
    """单个 chunk 的质量统计行（与 chunks 一对一）。

    关键字段：quality_score 综合分；like/dislike/correction 计数来自反馈；
    needs_review 标记需人工复核的 chunk。
    """

    __tablename__ = "chunk_quality"

    chunk_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True
    )
    quality_score: Mapped[float] = mapped_column(Float, default=0.5)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    dislike_count: Mapped[int] = mapped_column(Integer, default=0)
    correction_count: Mapped[int] = mapped_column(Integer, default=0)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
