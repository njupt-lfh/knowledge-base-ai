"""知识库服务"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.chroma_client import delete_collection
from ..models.document import Document
from ..models.knowledge_base import KnowledgeBase
from ..schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
)


class KnowledgeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self, page: int, page_size: int, search: str | None) -> tuple[list[KnowledgeBaseResponse], int]:
        query = select(KnowledgeBase)
        count_query = select(func.count(KnowledgeBase.id))

        if search:
            query = query.where(KnowledgeBase.name.contains(search))
            count_query = count_query.where(KnowledgeBase.name.contains(search))

        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.order_by(KnowledgeBase.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        kbs = result.scalars().all()

        items = []
        for kb in kbs:
            doc_count = (await self.db.execute(
                select(func.count(Document.id)).where(Document.knowledge_base_id == kb.id)
            )).scalar() or 0
            resp = KnowledgeBaseResponse(
                id=kb.id,
                name=kb.name,
                description=kb.description,
                embedding_model=kb.embedding_model,
                chunk_size=kb.chunk_size,
                chunk_overlap=kb.chunk_overlap,
                created_at=kb.created_at,
                updated_at=kb.updated_at,
                document_count=doc_count,
            )
            items.append(resp)

        return items, total

    async def create(self, data: KnowledgeBaseCreate) -> KnowledgeBaseResponse:
        kb = KnowledgeBase(
            name=data.name,
            description=data.description,
            chunk_size=data.chunk_size,
            chunk_overlap=data.chunk_overlap,
        )
        self.db.add(kb)
        await self.db.commit()
        await self.db.refresh(kb)
        return KnowledgeBaseResponse(
            id=kb.id,
            name=kb.name,
            description=kb.description,
            embedding_model=kb.embedding_model,
            chunk_size=kb.chunk_size,
            chunk_overlap=kb.chunk_overlap,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
            document_count=0,
        )

    async def get_by_id(self, kb_id: str) -> KnowledgeBaseResponse | None:
        kb = await self.db.get(KnowledgeBase, kb_id)
        if not kb:
            return None
        doc_count = (await self.db.execute(
            select(func.count(Document.id)).where(Document.knowledge_base_id == kb.id)
        )).scalar() or 0
        return KnowledgeBaseResponse(
            id=kb.id,
            name=kb.name,
            description=kb.description,
            embedding_model=kb.embedding_model,
            chunk_size=kb.chunk_size,
            chunk_overlap=kb.chunk_overlap,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
            document_count=doc_count,
        )

    async def update(self, kb_id: str, data: KnowledgeBaseUpdate) -> KnowledgeBaseResponse | None:
        kb = await self.db.get(KnowledgeBase, kb_id)
        if not kb:
            return None
        update_dict = data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(kb, key, value)
        await self.db.commit()
        await self.db.refresh(kb)
        return await self.get_by_id(kb_id)

    async def delete(self, kb_id: str):
        kb = await self.db.get(KnowledgeBase, kb_id)
        if kb:
            await self.db.delete(kb)
            await self.db.commit()
        delete_collection(kb_id)
