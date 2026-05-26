"""知识冲突裁决 — Phase 1.4"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.chroma_client import get_collection
from ..models.chunk import Chunk
from ..models.knowledge_conflict import KnowledgeConflict
from ..services.embedding_service import EmbeddingService


class ConflictService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.embed_svc = EmbeddingService()

    async def list_pending(self, kb_id: str, *, status: str | None = "pending") -> list[dict]:
        q = select(KnowledgeConflict).where(KnowledgeConflict.knowledge_base_id == kb_id)
        if status:
            q = q.where(KnowledgeConflict.status == status)
        q = q.order_by(KnowledgeConflict.created_at.desc())
        rows = (await self.db.execute(q)).scalars().all()
        return [await self._to_dict(row) for row in rows]

    async def resolve(self, kb_id: str, conflict_id: str, resolution: str) -> dict:
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
        return await self._to_dict(row)

    async def _to_dict(self, row: KnowledgeConflict) -> dict:
        existing = await self.db.get(Chunk, row.existing_chunk_id)
        return {
            "id": row.id,
            "kb_id": row.knowledge_base_id,
            "existing_chunk_id": row.existing_chunk_id,
            "existing_preview": (existing.content[:200] if existing else ""),
            "new_content": row.new_content,
            "new_preview": row.new_content[:200],
            "similarity": row.similarity,
            "status": row.status,
            "llm_reason": row.llm_reason,
            "source_document_id": row.source_document_id,
            "resolved_chunk_id": row.resolved_chunk_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        }
