"""答案一致性审核队列服务（Phase 2 · 导师建议 #3）。"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.answer_review_queue import REVIEW_STATUSES, AnswerReviewQueue
from ..utils.kb_id import KbIdResolver
from .gap_service import GapService

logger = logging.getLogger(__name__)


class AnswerReviewService:
    """双路径一致性 CONFLICT/UNCERTAIN 入队 + 关联 Gap。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _canonical_kb_id(self, kb_id: str) -> str:
        return await KbIdResolver(self.db).resolve(kb_id)

    async def list_reviews(
        self,
        kb_id: str,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[AnswerReviewQueue]:
        """列出知识库的待审核答案。"""
        canonical = await self._canonical_kb_id(kb_id)
        q = select(AnswerReviewQueue).where(AnswerReviewQueue.kb_id == canonical)
        if status:
            q = q.where(AnswerReviewQueue.status == status)
        q = q.order_by(AnswerReviewQueue.created_at.desc()).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def record_consistency_issue(
        self,
        *,
        kb_id: str,
        query: str,
        answer_a: str,
        answer_b: str,
        verdict: str,
        ctx_hash: str = "",
        reason: str = "",
        route: str | None = None,
        retrieval_sources: list[dict] | None = None,
        conversation_id: str | None = None,
        message_id: str | None = None,
    ) -> AnswerReviewQueue:
        """CONFLICT/UNCERTAIN 时写入审核队列并创建关联 Gap。"""
        if verdict not in ("CONFLICT", "UNCERTAIN"):
            raise ValueError(f"invalid verdict for review queue: {verdict}")

        canonical = await self._canonical_kb_id(kb_id)

        existing = await self.db.execute(
            select(AnswerReviewQueue).where(
                AnswerReviewQueue.kb_id == canonical,
                AnswerReviewQueue.query == query,
                AnswerReviewQueue.ctx_hash == ctx_hash,
                AnswerReviewQueue.status == "pending",
            )
        )
        dup = existing.scalar_one_or_none()
        if dup:
            return dup

        gap_svc = GapService(self.db)
        suggested = json.dumps(
            {
                "verdict": verdict,
                "answer_a": answer_a[:2000],
                "answer_b": answer_b[:2000],
                "reason": reason,
                "route": route,
                "ctx_hash": ctx_hash,
            },
            ensure_ascii=False,
        )
        gap = await gap_svc.create_gap(
            kb_id=canonical,
            query=query,
            gap_type="KNOWLEDGE_ABSENT",
            conversation_id=conversation_id,
            message_id=message_id,
            suggested_content=suggested,
            retrieval_result=retrieval_sources,
        )

        row = AnswerReviewQueue(
            kb_id=canonical,
            query=query,
            answer_a=answer_a,
            answer_b=answer_b,
            ctx_hash=ctx_hash or "",
            verdict=verdict,
            reason=reason or None,
            route=route,
            gap_id=gap.id,
            status="pending",
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        logger.info(
            "answer review queued kb=%s verdict=%s review_id=%s gap_id=%s",
            canonical,
            verdict,
            row.id,
            gap.id,
        )
        return row

    async def create_manual(
        self,
        kb_id: str,
        *,
        query: str,
        answer_a: str,
        answer_b: str,
        verdict: str = "CONFLICT",
        reason: str | None = None,
        route: str | None = None,
        ctx_hash: str = "",
    ) -> AnswerReviewQueue:
        """API 手动入队。"""
        return await self.record_consistency_issue(
            kb_id=kb_id,
            query=query,
            answer_a=answer_a,
            answer_b=answer_b,
            verdict=verdict,
            ctx_hash=ctx_hash,
            reason=reason or "",
            route=route,
        )

    async def update_status(
        self,
        review_id: str,
        *,
        status: str,
        assignee: str | None = None,
    ) -> AnswerReviewQueue | None:
        """更新审核工单状态。"""
        if status not in REVIEW_STATUSES:
            raise ValueError(f"invalid status: {status}")

        row = await self.db.get(AnswerReviewQueue, review_id)
        if not row:
            return None

        row.status = status
        if assignee is not None:
            row.assignee = assignee
        if status in ("resolved", "dismissed"):
            row.resolved_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(row)
        return row
