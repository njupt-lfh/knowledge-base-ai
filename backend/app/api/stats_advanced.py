"""Phase 4 进阶统计 API"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services import stats_service

router = APIRouter(tags=["stats-advanced"])


@router.get("/api/knowledge-bases/{kb_id}/stats/distribution")
async def kb_hit_distribution(kb_id: str, db: AsyncSession = Depends(get_db)):
    buckets = await stats_service.hit_distribution(db, kb_id)
    return {"buckets": buckets}


@router.get("/api/knowledge-bases/{kb_id}/stats/cite-vs-hit")
async def kb_cite_vs_hit(kb_id: str, limit: int = 10, db: AsyncSession = Depends(get_db)):
    items = await stats_service.cite_vs_hit(db, kb_id, limit=min(limit, 20))
    return {"items": items}


@router.get("/api/knowledge-bases/{kb_id}/stats/sankey")
async def kb_rag_sankey(kb_id: str, limit: int = 15, db: AsyncSession = Depends(get_db)):
    data = await stats_service.rag_sankey(db, kb_id, limit=min(limit, 30))
    return data


@router.get("/api/stats/activity-heatmap")
async def activity_heatmap(
    kb_id: str | None = None,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
):
    points = await stats_service.activity_heatmap(db, kb_id, days)
    return {"points": points}


@router.get("/api/stats/cold-knowledge")
async def cold_knowledge(
    kb_id: str | None = None,
    days: int = 90,
    db: AsyncSession = Depends(get_db),
):
    return await stats_service.cold_knowledge_count(db, kb_id, days)
