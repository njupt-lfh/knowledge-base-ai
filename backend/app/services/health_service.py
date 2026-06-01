"""知识库健康度聚合服务（Phase 1 审计修复）。

职责：
    汇总冷知识、待处理 Gap、冲突、低质量 chunk 等指标，
    输出 healthy / attention / critical 健康等级。

在流水线中的位置：
    API health 路由 → knowledge_base_health

依赖服务：
    - stats_service.cold_knowledge_count
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chunk import Chunk
from ..models.chunk_quality import ChunkQuality
from ..models.knowledge_conflict import KnowledgeConflict
from ..models.knowledge_gap import KnowledgeGap
from ..utils.kb_id import KbIdResolver
from .stats_service import cold_knowledge_count


async def knowledge_base_health(db: AsyncSession, kb_id: str) -> dict:
    """计算单知识库健康度快照。

    参数:
        db: 数据库会话
        kb_id: 知识库 ID（支持 legacy 前缀解析）

    返回:
        含 level、pending_gaps、冷知识统计等的字典
    """
    resolver = KbIdResolver(db)
    canonical = await resolver.resolve(kb_id)
    legacy = resolver.legacy_prefix(canonical)
    gap_kb_ids = [canonical] if legacy == canonical else [canonical, legacy]

    cold = await cold_knowledge_count(db, canonical)

    pending_gaps = (
        await db.execute(
            select(func.count(KnowledgeGap.id)).where(
                KnowledgeGap.kb_id.in_(gap_kb_ids),
                KnowledgeGap.status.in_(("pending", "suggested", "manual_required")),
            )
        )
    ).scalar() or 0

    pending_conflicts = (
        await db.execute(
            select(func.count(KnowledgeConflict.id)).where(
                KnowledgeConflict.knowledge_base_id == canonical,
                KnowledgeConflict.status == "pending",
            )
        )
    ).scalar() or 0

    low_quality = (
        await db.execute(
            select(func.count(ChunkQuality.chunk_id))
            .join(Chunk, Chunk.id == ChunkQuality.chunk_id)
            .where(Chunk.knowledge_base_id == canonical, ChunkQuality.needs_review.is_(True))
        )
    ).scalar() or 0

    total_chunks = (
        await db.execute(select(func.count(Chunk.id)).where(Chunk.knowledge_base_id == canonical))
    ).scalar() or 0

    active_chunks = (
        await db.execute(
            select(func.count(Chunk.id)).where(
                Chunk.knowledge_base_id == canonical, Chunk.is_active.is_(True)
            )
        )
    ).scalar() or 0

    attention_score = (
        int(cold["cold_count_90d"]) + int(pending_gaps) + int(pending_conflicts) + int(low_quality)
    )
    if attention_score == 0:
        level = "healthy"
    elif attention_score < 10:
        level = "attention"
    else:
        level = "critical"

    return {
        "kb_id": canonical,
        "level": level,
        "cold": cold,
        "pending_gaps": int(pending_gaps),
        "pending_conflicts": int(pending_conflicts),
        "low_quality_chunks": int(low_quality),
        "total_chunks": int(total_chunks),
        "active_chunks": int(active_chunks),
        "attention_score": attention_score,
    }
