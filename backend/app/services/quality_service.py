"""Chunk 质量分计算与检索加权 — Phase 1.2"""

from __future__ import annotations

import math
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chunk import Chunk
from ..models.chunk_quality import ChunkQuality

LOW_QUALITY_THRESHOLD = 0.25
REVIEW_DISLIKE_THRESHOLD = 3
RETRIEVAL_BLEND = 0.7  # retrieval_score 权重
QUALITY_BLEND = 0.3


def compute_quality_score(
    *,
    hit_count: int,
    like_count: int,
    dislike_count: int,
    correction_count: int,
    created_at: datetime | None,
) -> float:
    """统一版公式初版实现。"""
    hit_count = int(hit_count or 0)
    like_count = int(like_count or 0)
    dislike_count = int(dislike_count or 0)
    correction_count = int(correction_count or 0)
    norm_hit = min(hit_count / 20.0, 1.0)
    feedback_total = like_count + dislike_count
    like_rate = like_count / feedback_total if feedback_total > 0 else 0.5
    correction_rate = min(correction_count / max(hit_count, 1), 1.0)

    freshness = 1.0
    if created_at:
        days = (datetime.utcnow() - created_at).days
        freshness = max(0.0, 1.0 - days / 365.0)

    raw = (
        0.4 * norm_hit
        + 0.3 * like_rate
        - 0.2 * correction_rate
        + 0.1 * freshness
    )
    return round(max(0.0, min(1.0, raw)), 4)


def blend_retrieval_score(retrieval_score: float, quality_score: float) -> float:
    return round(RETRIEVAL_BLEND * retrieval_score + QUALITY_BLEND * quality_score, 4)


class QualityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create(self, chunk_id: str) -> ChunkQuality:
        result = await self.db.execute(
            select(ChunkQuality).where(ChunkQuality.chunk_id == chunk_id)
        )
        row = result.scalar_one_or_none()
        if row:
            return row
        row = ChunkQuality(chunk_id=chunk_id)
        self.db.add(row)
        await self.db.flush()
        return row

    async def recalculate_chunk(self, chunk_id: str) -> ChunkQuality | None:
        chunk = await self.db.get(Chunk, chunk_id)
        if not chunk:
            return None
        q = await self.get_or_create(chunk_id)
        q.like_count = q.like_count or 0
        q.dislike_count = q.dislike_count or 0
        q.correction_count = q.correction_count or 0
        q.quality_score = compute_quality_score(
            hit_count=chunk.hit_count or 0,
            like_count=q.like_count,
            dislike_count=q.dislike_count,
            correction_count=q.correction_count,
            created_at=chunk.created_at,
        )
        q.needs_review = (
            q.quality_score < LOW_QUALITY_THRESHOLD
            or q.dislike_count >= REVIEW_DISLIKE_THRESHOLD
        )
        q.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(q)
        return q

    async def apply_feedback(
        self,
        chunk_ids: list[str],
        feedback_type: str,
    ) -> list[ChunkQuality]:
        updated: list[ChunkQuality] = []
        for cid in chunk_ids:
            q = await self.get_or_create(cid)
            if feedback_type == "like":
                q.like_count += 1
            elif feedback_type == "dislike":
                q.dislike_count += 1
            elif feedback_type == "correction":
                q.correction_count += 1
            row = await self.recalculate_chunk(cid)
            if row:
                updated.append(row)
        return updated

    async def get_scores_map(self, chunk_ids: list[str]) -> dict[str, float]:
        if not chunk_ids:
            return {}
        result = await self.db.execute(
            select(ChunkQuality.chunk_id, ChunkQuality.quality_score).where(
                ChunkQuality.chunk_id.in_(chunk_ids)
            )
        )
        scores = {r[0]: r[1] for r in result.all()}
        missing = [cid for cid in chunk_ids if cid not in scores]
        for cid in missing:
            row = await self.recalculate_chunk(cid)
            if row:
                scores[cid] = row.quality_score
        return scores

    async def list_low_quality(self, kb_id: str, limit: int = 20) -> list[dict]:
        result = await self.db.execute(
            select(ChunkQuality, Chunk.content)
            .join(Chunk, Chunk.id == ChunkQuality.chunk_id)
            .where(
                Chunk.knowledge_base_id == kb_id,
                ChunkQuality.needs_review.is_(True),
            )
            .order_by(ChunkQuality.quality_score)
            .limit(limit)
        )
        return [
            {
                "chunk_id": q.chunk_id,
                "quality_score": q.quality_score,
                "like_count": q.like_count,
                "dislike_count": q.dislike_count,
                "correction_count": q.correction_count,
                "content_preview": (content or "")[:120],
            }
            for q, content in result.all()
        ]
