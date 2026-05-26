"""质量分 API — Phase 1.2"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services.quality_service import QualityService

router = APIRouter(prefix="/api/knowledge-bases/{kb_id}/quality", tags=["quality"])


@router.get("/low-quality")
async def list_low_quality_chunks(kb_id: str, limit: int = 20, db: AsyncSession = Depends(get_db)):
    svc = QualityService(db)
    return await svc.list_low_quality(kb_id, limit=limit)


@router.post("/recalculate")
async def recalculate_kb_quality(kb_id: str, db: AsyncSession = Depends(get_db)):
    """批量重算知识库内全部 chunk 质量分（管理/调试）。"""
    from sqlalchemy import select

    from ..models.chunk import Chunk

    svc = QualityService(db)
    rows = (await db.execute(select(Chunk.id).where(Chunk.knowledge_base_id == kb_id))).all()
    count = 0
    for (cid,) in rows:
        if await svc.recalculate_chunk(cid):
            count += 1
    return {"recalculated": count}
