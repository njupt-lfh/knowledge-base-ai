"""知识块服务"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.chroma_client import get_collection
from ..models.chunk import Chunk
from ..schemas.chunk import ChunkResponse, ChunkUpdate, SearchResultItem
from .embedding_service import EmbeddingService


class ChunkService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.embed_svc = EmbeddingService()

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
        return ChunkResponse.model_validate(chunk)

    async def toggle_status(self, chunk_id: str, is_active: bool) -> ChunkResponse:
        chunk = await self.db.get(Chunk, chunk_id)
        chunk.is_active = is_active
        self._sync_chroma_active(chunk)
        await self.db.commit()
        await self.db.refresh(chunk)
        return ChunkResponse.model_validate(chunk)

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
        """知识检索：向量相似度搜索（过滤已禁用的块）"""
        try:
            query_embedding = self.embed_svc.embed_query(query)
            collection = get_collection(kb_id)

            # 多取一些结果，留出过滤空间
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k * 3,
            )

            items = []
            if results.get("ids") and len(results["ids"][0]) > 0:
                # 批量查询 chunk 状态
                chunk_ids = results["ids"][0]
                active_map = {}
                db_result = await self.db.execute(
                    select(Chunk.id, Chunk.is_active).where(Chunk.id.in_(chunk_ids))
                )
                for row in db_result:
                    active_map[row.id] = row.is_active

                count = 0
                for i, chunk_id in enumerate(chunk_ids):
                    if not active_map.get(chunk_id, True):
                        continue
                    distance = results["distances"][0][i] if results.get("distances") else 0
                    score = 1 - distance
                    if score > 0.3:
                        items.append(SearchResultItem(
                            chunk_id=chunk_id,
                            content=results["documents"][0][i][:200],
                            score=round(score, 4),
                            document_id=results["metadatas"][0][i].get("document_id", ""),
                            chunk_index=results["metadatas"][0][i].get("chunk_index", 0),
                        ))
                        count += 1
                        if count >= top_k:
                            break

            # 热度统计：递增命中次数
            if items:
                try:
                    hit_ids = [it.chunk_id for it in items]
                    await self.db.execute(
                        select(Chunk).where(Chunk.id.in_(hit_ids))
                    )
                    for chunk_id in hit_ids:
                        chunk = await self.db.get(Chunk, chunk_id)
                        if chunk:
                            chunk.hit_count = (chunk.hit_count or 0) + 1
                    await self.db.commit()
                except Exception:
                    pass

            return items
        except Exception:
            return []
