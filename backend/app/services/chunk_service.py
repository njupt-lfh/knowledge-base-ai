"""知识块（Chunk）CRUD 与检索服务。

职责：
    管理 chunk 的列表、更新、启停，同步 Chroma / FTS5 / 图谱，
    并提供与 RAG 一致的 Hybrid 搜索 API。

在流水线中的位置：
    API 层 chunk 路由 → ChunkService
    治理/冲突 → ChunkService.toggle_status

依赖服务：
    - HybridRetriever：混合检索
    - EmbeddingService：向量同步
    - fts_service、graph_store_service：索引同步
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.chroma_client import get_collection
from ..models.chunk import Chunk
from ..schemas.chunk import ChunkResponse, ChunkUpdate, SearchResultItem
from .embedding_service import EmbeddingService
from .hybrid_retriever import HybridRetriever


class ChunkService:
    """Chunk 业务服务：CRUD + 三索引同步 + Hybrid 搜索。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.retriever = HybridRetriever()
        self.embed_svc = EmbeddingService()

    async def list_by_document(self, doc_id: str) -> list[ChunkResponse]:
        """列出文档下全部 chunk（按 chunk_index 排序）。

        参数:
            doc_id: 文档 ID

        返回:
            ChunkResponse 列表
        """
        result = await self.db.execute(
            select(Chunk).where(Chunk.document_id == doc_id).order_by(Chunk.chunk_index)
        )
        return [ChunkResponse.model_validate(c) for c in result.scalars().all()]

    async def update(self, chunk_id: str, data: ChunkUpdate) -> ChunkResponse | None:
        """更新 chunk 内容与/或活跃状态，并同步各索引。

        参数:
            chunk_id: chunk ID
            data: 更新字段

        返回:
            更新后的 ChunkResponse，不存在则 None
        """
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
        """启用/禁用 chunk，同步向量与 FTS/图谱。

        参数:
            chunk_id: chunk ID
            is_active: 目标状态

        返回:
            更新后的 ChunkResponse
        """
        chunk = await self.db.get(Chunk, chunk_id)
        chunk.is_active = is_active
        self._sync_chroma_active(chunk)
        await self.db.commit()
        await self.db.refresh(chunk)
        await self._sync_fts(chunk)
        return ChunkResponse.model_validate(chunk)

    async def _sync_fts(self, chunk: Chunk) -> None:
        """同步 FTS5 索引并触发图谱同步。

        参数:
            chunk: chunk 实体
        """
        from .fts_service import upsert_chunk_fts

        await upsert_chunk_fts(
            self.db, chunk.id, chunk.knowledge_base_id, chunk.content, active=chunk.is_active
        )
        await self.db.commit()
        await self._sync_graph(chunk)

    async def _sync_graph(self, chunk: Chunk) -> None:
        """同步知识图谱三元组。

        参数:
            chunk: chunk 实体
        """
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
        """同步 Chroma：启用时 upsert 向量，禁用时 delete。

        参数:
            chunk: chunk 实体
        """
        try:
            collection = get_collection(chunk.knowledge_base_id)
            if chunk.is_active:
                embedding = self.embed_svc.embed_query(chunk.content)
                collection.upsert(
                    ids=[chunk.id],
                    embeddings=[embedding],
                    documents=[chunk.content],
                    metadatas=[
                        {"document_id": chunk.document_id, "chunk_index": chunk.chunk_index}
                    ],
                )
            else:
                collection.delete(ids=[chunk.id])
        except Exception:
            pass

    def _sync_chroma_embedding(self, chunk: Chunk):
        """内容更新时重新向量化并 upsert Chroma。

        参数:
            chunk: chunk 实体
        """
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
        """Hybrid 检索（与 RAG 路径一致：Vector + FTS5 + RRF + Rerank）。

        参数:
            kb_id: 知识库 ID
            query: 查询文本
            top_k: 返回条数

        返回:
            SearchResultItem 列表
        """
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
