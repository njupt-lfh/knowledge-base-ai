"""标签 ORM 模型。

定义 `Tag` 与 `DocumentTag` 多对多关联表，支持按知识库维度的文档分类标签。
"""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class Tag(Base):
    """知识库内标签定义。

    关键字段：knowledge_base_id 限定标签作用域；name 为展示与筛选用的标签名。
    """

    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    knowledge_base_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)


class DocumentTag(Base):
    """文档与标签的关联行。

    关键字段：document_id 与 tag_id 构成多对多中间表，删除文档或标签时级联清理。
    """

    __tablename__ = "document_tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    tag_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False
    )
