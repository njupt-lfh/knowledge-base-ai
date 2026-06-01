"""知识库 ORM 模型。

定义 `KnowledgeBase` 表，作为文档、分块、标签等业务数据的顶层容器，
并存储分块与 Embedding 模型等 per-KB 配置。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base

if TYPE_CHECKING:
    from .document import Document


class KnowledgeBase(Base):
    """知识库实体。

    关键字段：name/description 展示信息；embedding_model/chunk_size/chunk_overlap
    控制入库与检索行为；documents 关联该库下全部文档（级联删除）。
    """

    __tablename__ = "knowledge_bases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str] = mapped_column(
        String(255), default="doubao-embedding-text-240715"
    )
    chunk_size: Mapped[int] = mapped_column(Integer, default=500)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=50)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    documents: Mapped[list[Document]] = relationship(
        "Document", back_populates="knowledge_base", cascade="all, delete-orphan"
    )
