"""Chunk 质量分 API 路由（Phase 1.2）。

提供低质量 chunk 列表与全库质量分重算端点，
委托 `QualityService` 基于用户反馈聚合评分。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services.quality_service import QualityService

router = APIRouter(prefix="/api/knowledge-bases/{kb_id}/quality", tags=["quality"])


@router.get("/low-quality")
async def list_low_quality_chunks(kb_id: str, limit: int = 20, db: AsyncSession = Depends(get_db)):
    """列出知识库内质量分较低的 chunk。

    参数:
        kb_id: 知识库 ID。
        limit: 最大返回条数。
        db: 数据库会话。

    返回:
        低质量 chunk 列表（由 QualityService 定义）。
    """
    svc = QualityService(db)
    return await svc.list_low_quality(kb_id, limit=limit)


@router.post("/recalculate")
async def recalculate_kb_quality(kb_id: str, db: AsyncSession = Depends(get_db)):
    """批量重算知识库内全部 chunk 质量分（管理/调试用）。

    参数:
        kb_id: 知识库 ID。
        db: 数据库会话。

    返回:
        含 recalculated 成功重算数量的字典。
    """
    from sqlalchemy import select

    from ..models.chunk import Chunk

    svc = QualityService(db)
    rows = (await db.execute(select(Chunk.id).where(Chunk.knowledge_base_id == kb_id))).all()
    count = 0
    for (cid,) in rows:
        if await svc.recalculate_chunk(cid):
            count += 1
    return {"recalculated": count}
