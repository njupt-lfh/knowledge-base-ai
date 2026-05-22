"""知识块服务"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.chunk import Chunk
from ..schemas.chunk import ChunkUpdate, ChunkResponse, SearchResultItem


class ChunkService:
    def __init__(self, db: AsyncSession):
        self.db = db

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

    async def search(self, kb_id: str, query: str, top_k: int) -> list[SearchResultItem]:
        """知识检索 - 目前返回空（需要向量化服务）"""
        # TODO: 接入 EmbeddingService 和 Chroma
        return []
