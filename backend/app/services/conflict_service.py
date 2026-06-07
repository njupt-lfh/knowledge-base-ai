"""知识冲突裁决服务（Phase 1.4）。

职责：
    管理入库门禁产生的 KnowledgeConflict 待办，
    支持保留新/旧/驳回等裁决并同步 Chroma。

在流水线中的位置：
    API conflicts 路由 → ConflictService

依赖服务：
    - EmbeddingService：裁决保留新版本时写入向量
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.chroma_client import get_collection
from ..models.chunk import Chunk
from ..models.document import Document
from ..models.knowledge_conflict import KnowledgeConflict
from ..services.embedding_service import EmbeddingService


class ConflictService:
    """知识冲突列表与裁决。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.embed_svc = EmbeddingService()

    async def list_pending(self, kb_id: str, *, status: str | None = "pending") -> list[dict]:
        """列出冲突记录。

        参数:
            kb_id: 知识库 ID
            status: 过滤状态，None 表示全部

        返回:
            冲突 dict 列表
        """
        q = select(KnowledgeConflict).where(KnowledgeConflict.knowledge_base_id == kb_id)
        if status:
            q = q.where(KnowledgeConflict.status == status)
        q = q.order_by(KnowledgeConflict.created_at.desc())
        rows = (await self.db.execute(q)).scalars().all()
        refs_map = await self._load_chunk_refs_map(
            {row.existing_chunk_id for row in rows}, kb_id=kb_id
        )
        doc_names = await self._load_document_names(
            {row.source_document_id for row in rows if row.source_document_id}
        )
        return [self._serialize(row, refs_map, doc_names) for row in rows]

    async def resolve(self, kb_id: str, conflict_id: str, resolution: str) -> dict:
        """裁决冲突。

        参数:
            kb_id: 知识库 ID
            conflict_id: 冲突 ID
            resolution: resolved_keep_new | resolved_keep_old | dismissed

        返回:
            更新后的冲突 dict

        Raises:
            ValueError: 冲突不存在或已裁决
        """
        row = await self.db.get(KnowledgeConflict, conflict_id)
        if not row or row.knowledge_base_id != kb_id:
            raise ValueError("conflict not found")
        if row.status != "pending":
            raise ValueError("conflict already resolved")

        if resolution == "resolved_keep_new":
            existing = await self.db.get(Chunk, row.existing_chunk_id)
            if not existing:
                raise ValueError("existing chunk missing")
            doc_id = row.source_document_id or existing.document_id
            chunk = Chunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                knowledge_base_id=kb_id,
                content=row.new_content,
                chunk_index=0,
                char_count=len(row.new_content),
            )
            self.db.add(chunk)
            await self.db.flush()
            emb = self.embed_svc.embed_query(chunk.content)
            collection = get_collection(kb_id)
            collection.upsert(
                ids=[chunk.id],
                embeddings=[emb],
                documents=[chunk.content],
                metadatas=[{"document_id": chunk.document_id, "chunk_index": chunk.chunk_index}],
            )
            row.resolved_chunk_id = chunk.id
            row.status = "resolved_keep_new"
        elif resolution == "resolved_keep_old":
            row.status = "resolved_keep_old"
        elif resolution == "dismissed":
            row.status = "dismissed"
        else:
            raise ValueError(f"unknown resolution: {resolution}")

        row.resolved_at = datetime.utcnow()
        await self.db.commit()
        refs_map = await self._load_chunk_refs_map({row.existing_chunk_id}, kb_id=kb_id)
        doc_names = await self._load_document_names(
            {row.source_document_id} if row.source_document_id else set()
        )
        return self._serialize(row, refs_map, doc_names)

    async def _load_chunk_refs_map(
        self, chunk_ids: set[str] | list[str], *, kb_id: str | None = None
    ) -> dict[str, dict[str, Any]]:
        ids = [cid for cid in chunk_ids if cid]
        if not ids:
            return {}
        filters = [Chunk.id.in_(ids)]
        if kb_id:
            filters.append(Chunk.knowledge_base_id == kb_id)
        rows = await self.db.execute(
            select(Chunk, Document.filename)
            .join(Document, Chunk.document_id == Document.id)
            .where(*filters)
        )
        out: dict[str, dict[str, Any]] = {}
        for chunk, filename in rows.all():
            out[chunk.id] = {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "document_name": filename,
                "chunk_index": chunk.chunk_index,
                "is_active": chunk.is_active,
                "preview": (chunk.content or "")[:200],
            }
        return out

    async def _load_document_names(self, document_ids: set[str] | list[str]) -> dict[str, str]:
        ids = [did for did in document_ids if did]
        if not ids:
            return {}
        rows = await self.db.execute(
            select(Document.id, Document.filename).where(Document.id.in_(ids))
        )
        return {doc_id: filename for doc_id, filename in rows.all()}

    def _serialize(
        self,
        row: KnowledgeConflict,
        refs_map: dict[str, dict[str, Any]],
        doc_names: dict[str, str],
    ) -> dict:
        """ORM 转 API dict。

        参数:
            row: KnowledgeConflict 实体
            refs_map: existing_chunk_id → 来源信息
            doc_names: source_document_id → 文档名

        返回:
            序列化字典
        """
        existing_ref = refs_map.get(row.existing_chunk_id)
        existing_preview = existing_ref["preview"] if existing_ref else ""
        return {
            "id": row.id,
            "kb_id": row.knowledge_base_id,
            "existing_chunk_id": row.existing_chunk_id,
            "existing_chunk_ref": existing_ref,
            "existing_preview": existing_preview,
            "new_content": row.new_content,
            "new_preview": row.new_content[:200],
            "similarity": row.similarity,
            "status": row.status,
            "llm_reason": row.llm_reason,
            "source_document_id": row.source_document_id,
            "source_document_name": doc_names.get(row.source_document_id or "", None),
            "resolved_chunk_id": row.resolved_chunk_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        }
