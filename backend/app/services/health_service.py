"""知识库健康度聚合 — Phase 1 审计修复"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chunk import Chunk
from ..models.chunk_quality import ChunkQuality
from ..models.knowledge_conflict import KnowledgeConflict
from ..models.knowledge_gap import KnowledgeGap
from .stats_service import cold_knowledge_count


async def knowledge_base_health(db: AsyncSession, kb_id: str) -> dict:
    cold = await cold_knowledge_count(db, kb_id)

    pending_gaps = (
        await db.execute(
            select(func.count(KnowledgeGap.id)).where(
                KnowledgeGap.kb_id == kb_id,
                KnowledgeGap.status.in_(("pending", "suggested", "manual_required")),
            )
        )
    ).scalar() or 0

    pending_conflicts = (
        await db.execute(
            select(func.count(KnowledgeConflict.id)).where(
                KnowledgeConflict.knowledge_base_id == kb_id,
                KnowledgeConflict.status == "pending",
            )
        )
    ).scalar() or 0

    low_quality = (
        await db.execute(
            select(func.count(ChunkQuality.chunk_id))
            .join(Chunk, Chunk.id == ChunkQuality.chunk_id)
            .where(Chunk.knowledge_base_id == kb_id, ChunkQuality.needs_review.is_(True))
        )
    ).scalar() or 0

    total_chunks = (
        await db.execute(
            select(func.count(Chunk.id)).where(Chunk.knowledge_base_id == kb_id)
        )
    ).scalar() or 0

    active_chunks = (
        await db.execute(
            select(func.count(Chunk.id)).where(
                Chunk.knowledge_base_id == kb_id, Chunk.is_active.is_(True)
            )
        )
    ).scalar() or 0

    attention_score = int(cold["cold_count_90d"]) + int(pending_gaps) + int(pending_conflicts) + int(low_quality)
    if attention_score == 0:
        level = "healthy"
    elif attention_score < 10:
        level = "attention"
    else:
        level = "critical"

    return {
        "kb_id": kb_id,
        "level": level,
        "cold": cold,
        "pending_gaps": int(pending_gaps),
        "pending_conflicts": int(pending_conflicts),
        "low_quality_chunks": int(low_quality),
        "total_chunks": int(total_chunks),
        "active_chunks": int(active_chunks),
        "attention_score": attention_score,
    }
