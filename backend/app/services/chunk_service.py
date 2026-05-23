"""知识块服务"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.chroma_client import get_collection
from .embedding_service import EmbeddingService
from ..models.chunk import Chunk
from ..schemas.chunk import ChunkResponse, ChunkUpdate, SearchResultItem


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
        if data.is_active is not None:
            chunk.is_active = data.is_active
        await self.db.commit()
        await self.db.refresh(chunk)
        return ChunkResponse.model_validate(chunk)

    async def toggle_status(self, chunk_id: str, is_active: bool) -> ChunkResponse:
        chunk = await self.db.get(Chunk, chunk_id)
        chunk.is_active = is_active
        await self.db.commit()
        await self.db.refresh(chunk)
        return ChunkResponse.model_validate(chunk)

    async def search(self, kb_id: str, query: str, top_k: int = 5) -> list[SearchResultItem]:
        """知识检索：向量相似度搜索"""
        try:
            query_embedding = self.embed_svc.embed_query(query)
            collection = get_collection(kb_id)

            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
            )

            items = []
            if results.get("ids") and len(results["ids"][0]) > 0:
                for i, chunk_id in enumerate(results["ids"][0]):
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
            return items
        except Exception:
            return []
