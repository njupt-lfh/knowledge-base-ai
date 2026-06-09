"""Chunk 质量分计算与检索加权服务（Phase 1.2）。

职责：
    基于命中、点赞/点踩、纠正次数、新鲜度计算 chunk 质量分，
    并在 Hybrid 检索最终排序时与 retrieval_score 加权融合。

在流水线中的位置：
    HybridRetriever.search → QualityService.get_scores_map
    FeedbackService → apply_feedback

依赖：Chunk、ChunkQuality 模型
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chunk import Chunk
from ..models.chunk_quality import ChunkQuality

LOW_QUALITY_THRESHOLD = 0.25
REVIEW_DISLIKE_THRESHOLD = 3
RETRIEVAL_BLEND = 0.7  # retrieval_score 权重
QUALITY_BLEND = 0.3
# 质量门控硬过滤阈值（Phase 1）
QUALITY_GATE_MIN_SCORE = 0.2  # 低于此分的 chunk 禁止进入检索结果（放行冷启动 ~0.247+）
QUALITY_GATE_DISLIKE_BLACKLIST = 3  # 点踩数达到此值进入黑名单
QUALITY_GATE_NEEDS_REVIEW_DISLIKE = 2  # needs_review 且 dislike 达到此值即剔除


def compute_quality_score(
    *,
    hit_count: int,
    like_count: int,
    dislike_count: int,
    correction_count: int,
    created_at: datetime | None,
) -> float:
    """统一版质量分公式。

    参数:
        hit_count: 检索命中次数
        like_count: 点赞数
        dislike_count: 点踩数
        correction_count: 纠正次数
        created_at: chunk 创建时间

    返回:
        质量分 [0, 1]
    """
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

    raw = 0.4 * norm_hit + 0.3 * like_rate - 0.2 * correction_rate + 0.1 * freshness
    return round(max(0.0, min(1.0, raw)), 4)


def blend_retrieval_score(retrieval_score: float, quality_score: float) -> float:
    """检索分与质量分线性融合。

    参数:
        retrieval_score: 混合检索分数
        quality_score: chunk 质量分

    返回:
        融合后的最终 score
    """
    return round(RETRIEVAL_BLEND * retrieval_score + QUALITY_BLEND * quality_score, 4)


def apply_quality_gate(
    candidates: list[dict],
    *,
    quality_scores: dict[str, float],
    quality_details: dict[str, dict] | None = None,
    min_score: float | None = None,
) -> list[dict]:
    """检索末段硬过滤：低质量 / needs_review+dislike / 黑名单 chunk 剔除。

    参数:
        candidates: 候选 chunk 列表，每个需含 'chunk_id' 或 'id'
        quality_scores: chunk_id → quality_score 映射
        quality_details: chunk_id → {like_count, dislike_count, needs_review} 映射（可选）
        min_score: 自定义最低质量分（默认 QUALITY_GATE_MIN_SCORE）

    返回:
        过滤后的候选列表（可能为空）
    """
    if not candidates:
        return []

    threshold = min_score if min_score is not None else QUALITY_GATE_MIN_SCORE
    details = quality_details or {}
    passed: list[dict] = []

    for c in candidates:
        cid = c.get("chunk_id") or c.get("id") or ""
        qs = quality_scores.get(cid, 0.5)  # 新 chunk 默认 0.5

        # 黑名单：dislike >= 3
        d = details.get(cid, {})
        dislike = d.get("dislike_count", 0)
        if dislike >= QUALITY_GATE_DISLIKE_BLACKLIST:
            continue

        # needs_review 且 dislike >= 2
        if d.get("needs_review") and dislike >= QUALITY_GATE_NEEDS_REVIEW_DISLIKE:
            continue

        # 质量分低于阈值
        if qs < threshold:
            continue

        passed.append(c)

    return passed


class QualityService:
    """Chunk 质量分 CRUD 与反馈更新。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create(self, chunk_id: str) -> ChunkQuality:
        """获取或创建 ChunkQuality 记录。

        参数:
            chunk_id: chunk ID

        返回:
            ChunkQuality 实体
        """
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
        """根据 Chunk 与反馈重新计算质量分。

        参数:
            chunk_id: chunk ID

        返回:
            更新后的 ChunkQuality 或 None
        """
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
            q.quality_score < LOW_QUALITY_THRESHOLD or q.dislike_count >= REVIEW_DISLIKE_THRESHOLD
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
        """批量应用用户反馈并重算质量分。

        参数:
            chunk_ids: 关联 chunk ID 列表
            feedback_type: like | dislike | correction

        返回:
            更新后的 ChunkQuality 列表
        """
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
        """批量获取 chunk 质量分（缺失则现场计算）。

        参数:
            chunk_ids: chunk ID 列表

        返回:
            chunk_id → quality_score 映射
        """
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

    async def get_quality_details_map(self, chunk_ids: list[str]) -> dict[str, dict]:
        """批量获取 chunk 的质量详情（dislike_count, needs_review 等）。

        用于 apply_quality_gate 的 blacklist / needs_review 规则。

        参数:
            chunk_ids: chunk ID 列表

        返回:
            chunk_id → {dislike_count, like_count, needs_review, quality_score} 映射
        """
        if not chunk_ids:
            return {}
        result = await self.db.execute(
            select(ChunkQuality).where(ChunkQuality.chunk_id.in_(chunk_ids))
        )
        return {
            r.chunk_id: {
                "dislike_count": r.dislike_count or 0,
                "like_count": r.like_count or 0,
                "needs_review": bool(r.needs_review),
                "quality_score": r.quality_score or 0.5,
            }
            for r in result.scalars().all()
        }

    async def list_low_quality(self, kb_id: str, limit: int = 20) -> list[dict]:
        """列出需复审的低质量 chunk。

        参数:
            kb_id: 知识库 ID
            limit: 最大条数

        返回:
            预览 dict 列表
        """
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
