"""知识图谱 API — Phase 3"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services.graph_store_service import graph_snapshot

router = APIRouter(prefix="/api/knowledge-bases", tags=["graph"])


@router.get("/{kb_id}/graph")
async def get_knowledge_graph(kb_id: str, limit: int = 80, db: AsyncSession = Depends(get_db)):
    snap = await graph_snapshot(db, kb_id, limit_nodes=min(limit, 200))
    if snap["relation_count"] == 0:
        return {**snap, "empty": True}
    return {**snap, "empty": False}
