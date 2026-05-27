"""知识块服务"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chunk import Chunk
from ..schemas.chunk import ChunkResponse, ChunkUpdate, SearchResultItem
from .hybrid_retriever import HybridRetriever


class ChunkService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.retriever = HybridRetriever()

    async def list_by_document(self, doc_id: str) -> list[ChunkResponse]:
        result = await self.db.execute(
            select(Chunk)
            .where(Chunk.document_id == doc_id)
            .order_by(Chunk.chunk_index)
        )
        return [ChunkResponse.model_validate(c) for c in result.scalars().all()]

    async def update(self, chunk_id: str, data: ChunkUpdate) -> ChunkResponse | None:
        chunk = await self.db.get(Chunk, chunk_id)
        if not chunk:
            return None
        if data.content is not None:
            chunk.content = data.content
            chunk.char_count = len(data.content)
            self._sync_chroma_embedding(chunk)
        if data.is_active is not None:
            chunk.is_active = data.is_active
            self._sync_chroma_active(chunk)
        await self.db.commit()
        await self.db.refresh(chunk)
        await self._sync_fts(chunk)
        return ChunkResponse.model_validate(chunk)

    async def toggle_status(self, chunk_id: str, is_active: bool) -> ChunkResponse:
        chunk = await self.db.get(Chunk, chunk_id)
        chunk.is_active = is_active
        self._sync_chroma_active(chunk)
        await self.db.commit()
        await self.db.refresh(chunk)
        await self._sync_fts(chunk)
        return ChunkResponse.model_validate(chunk)

    async def _sync_fts(self, chunk: Chunk) -> None:
        from .fts_service import upsert_chunk_fts

        await upsert_chunk_fts(
            self.db, chunk.id, chunk.knowledge_base_id, chunk.content, active=chunk.is_active
        )
        await self.db.commit()
        await self._sync_graph(chunk)

    async def _sync_graph(self, chunk: Chunk) -> None:
        from .graph_store_service import sync_chunk_graph

        await sync_chunk_graph(
            self.db,
            chunk.knowledge_base_id,
            chunk.id,
            chunk.document_id,
            chunk.content,
            active=chunk.is_active,
        )

    def _sync_chroma_active(self, chunk: Chunk):
        """同步 Chroma：启用时添加向量，禁用时删除"""
        try:
            collection = get_collection(chunk.knowledge_base_id)
            if chunk.is_active:
                embedding = self.embed_svc.embed_query(chunk.content)
                collection.upsert(
                    ids=[chunk.id],
                    embeddings=[embedding],
                    documents=[chunk.content],
                    metadatas=[{"document_id": chunk.document_id, "chunk_index": chunk.chunk_index}],
                )
            else:
                collection.delete(ids=[chunk.id])
        except Exception:
            pass

    def _sync_chroma_embedding(self, chunk: Chunk):
        """内容更新时重新向量化"""
        try:
            collection = get_collection(chunk.knowledge_base_id)
            embedding = self.embed_svc.embed_query(chunk.content)
            collection.upsert(
                ids=[chunk.id],
                embeddings=[embedding],
                documents=[chunk.content],
                metadatas=[{"document_id": chunk.document_id, "chunk_index": chunk.chunk_index}],
            )
        except Exception:
            pass

    async def search(self, kb_id: str, query: str, top_k: int = 5) -> list[SearchResultItem]:
        """Hybrid 检索（与 RAG 路径一致：Vector + FTS5 + RRF + Rerank）。"""
        try:
            hits = await self.retriever.search(self.db, kb_id, query, top_k=top_k)
            items = [
                SearchResultItem(
                    chunk_id=h["chunk_id"],
                    content=(h.get("content") or "")[:200],
                    score=round(float(h.get("score") or 0), 4),
                    document_id=h.get("document_id", ""),
                    chunk_index=h.get("chunk_index", 0),
                )
                for h in hits
            ]

            if items:
                try:
                    for it in items:
                        chunk = await self.db.get(Chunk, it.chunk_id)
                        if chunk:
                            chunk.hit_count = (chunk.hit_count or 0) + 1
                    await self.db.commit()
                except Exception:
                    pass

            return items
        except Exception:
            return []
