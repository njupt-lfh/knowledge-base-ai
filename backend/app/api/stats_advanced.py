"""Phase 4 进阶统计 API 路由。

提供命中分布、引用 vs 命中对比、RAG Sankey、活动热力图与冷知识统计，
委托 `stats_service` 聚合分析数据。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services import stats_service

router = APIRouter(tags=["stats-advanced"])


@router.get("/api/knowledge-bases/{kb_id}/stats/doc-types")
async def kb_doc_type_distribution(kb_id: str, db: AsyncSession = Depends(get_db)):
    """单库文档类型占比（PDF / Markdown / TXT 等）。

    参数:
        kb_id: 知识库 ID。
        db: 数据库会话。

    返回:
        含 items 的类型分布列表。
    """
    items = await stats_service.doc_type_distribution(db, kb_id)
    return {"items": items}


@router.get("/api/knowledge-bases/{kb_id}/stats/distribution")
async def kb_hit_distribution(kb_id: str, db: AsyncSession = Depends(get_db)):
    """知识库 chunk 命中次数分布直方图数据。

    参数:
        kb_id: 知识库 ID。
        db: 数据库会话。

    返回:
        含 buckets 的字典。
    """
    buckets = await stats_service.hit_distribution(db, kb_id)
    return {"buckets": buckets}


@router.get("/api/knowledge-bases/{kb_id}/stats/cite-vs-hit")
async def kb_cite_vs_hit(kb_id: str, limit: int = 10, db: AsyncSession = Depends(get_db)):
    """对比 chunk 被 RAG 引用次数与检索命中次数。

    参数:
        kb_id: 知识库 ID。
        limit: 返回条数上限（最大 20）。
        db: 数据库会话。

    返回:
        含 items 的对比列表。
    """
    items = await stats_service.cite_vs_hit(db, kb_id, limit=min(limit, 20))
    return {"items": items}


@router.get("/api/knowledge-bases/{kb_id}/stats/sankey")
async def kb_rag_sankey(kb_id: str, limit: int = 15, db: AsyncSession = Depends(get_db)):
    """RAG 检索→文档→chunk 流向 Sankey 图数据。

    参数:
        kb_id: 知识库 ID。
        limit: 边/节点数量上限（最大 30）。
        db: 数据库会话。

    返回:
        Sankey 节点与链接结构。
    """
    data = await stats_service.rag_sankey(db, kb_id, limit=min(limit, 30))
    return data


@router.get("/api/stats/activity-heatmap")
async def activity_heatmap(
    kb_id: str | None = None,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
):
    """平台或单库检索/对话活动热力图时间序列。

    参数:
        kb_id: 可选知识库 ID。
        days: 回溯天数。
        db: 数据库会话。

    返回:
        含 points 的热力图数据。
    """
    points = await stats_service.activity_heatmap(db, kb_id, days)
    return {"points": points}


@router.get("/api/stats/cold-knowledge")
async def cold_knowledge(
    kb_id: str | None = None,
    days: int = 90,
    db: AsyncSession = Depends(get_db),
):
    """统计长期未被检索命中的「冷知识」chunk 数量。

    参数:
        kb_id: 可选知识库 ID。
        days: 冷知识判定窗口天数。
        db: 数据库会话。

    返回:
        冷知识统计结果（由 stats_service 定义）。
    """
    return await stats_service.cold_knowledge_count(db, kb_id, days)
