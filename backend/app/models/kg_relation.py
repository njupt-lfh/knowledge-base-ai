"""轻量知识图谱 ORM 模型（Phase 3）。

定义 `KgRelation` 表，存储从 chunk 抽取的主谓宾三元组，
供图谱可视化与多跳检索扩展使用。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class KgRelation(Base):
    """实体关系三元组。

    关键字段：subject/predicate/object_entity 构成图边；chunk_id/document_id
    溯源；confidence/is_active 控制可信度与是否参与检索。
    同一 chunk 下相同三元组通过唯一约束去重。
    """

    __tablename__ = "kg_relations"
    __table_args__ = (
        UniqueConstraint(
            "knowledge_base_id",
            "chunk_id",
            "subject",
            "predicate",
            "object_entity",
            name="uq_kg_relation_chunk_triple",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    knowledge_base_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String(128), nullable=False)
    predicate: Mapped[str] = mapped_column(String(64), nullable=False)
    object_entity: Mapped[str] = mapped_column(String(128), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
