"""知识图谱 API 路由（Phase 3）。

只读返回知识库内抽取的三元组图快照，供前端可视化，
委托 `graph_store_service.graph_snapshot` 聚合节点与边。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services.graph_store_service import graph_snapshot

router = APIRouter(prefix="/api/knowledge-bases", tags=["graph"])


@router.get("/{kb_id}/graph")
async def get_knowledge_graph(kb_id: str, limit: int = 80, db: AsyncSession = Depends(get_db)):
    """获取知识库轻量图谱快照。

    参数:
        kb_id: 知识库 ID。
        limit: 最大节点数，内部 capped 为 200。
        db: 数据库会话。

    返回:
        含 nodes/edges/relation_count 及 empty 标记的字典。
    """
    snap = await graph_snapshot(db, kb_id, limit_nodes=min(limit, 200))
    if snap["relation_count"] == 0:
        return {**snap, "empty": True}
    return {**snap, "empty": False}
