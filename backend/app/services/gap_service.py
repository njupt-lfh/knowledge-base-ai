"""知识缺口队列服务 — classify_gap + 入库"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.chroma_client import get_collection
from ..models.knowledge_gap import GAP_STATUSES, GAP_TYPES, KnowledgeGap
from .embedding_service import EmbeddingService

# 弱命中：向量距离换算 score 高于此值，但未进入最终 context
WEAK_HIT_SCORE = 0.25
# 库内无相关证据
ABSENT_SCORE = 0.2
# 与 rag_service.SYSTEM_PROMPT 拒答话术保持一致（中英文）
NO_INFO_PHRASES = (
    "暂无相关信息",
    "暂无相关内容",
    "知识库中暂无",
    "目前知识库中暂无",
    "没有相关信息",
    "未找到相关",
    "无法找到相关",
    "no relevant information",
    "no information available",
    "not found in the knowledge",
)


class GapService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.embed_svc = EmbeddingService()

    def classify_gap(
        self,
        query: str,
        kb_id: str,
        retrieval_result: list[dict],
        *,
        correction_text: str | None = None,
        user_message: str | None = None,
    ) -> str:
        if correction_text and correction_text.strip():
            return "USER_CORRECTION"

        if user_message and self._looks_like_user_fact(user_message):
            return "USER_PROVIDED"

        if not retrieval_result:
            weak = self._probe_weak_hits(kb_id, query)
            return "RETRIEVAL_MISS" if weak else "KNOWLEDGE_ABSENT"

        max_score = max((s.get("score") or 0) for s in retrieval_result)
        if max_score < ABSENT_SCORE:
            weak = self._probe_weak_hits(kb_id, query)
            return "RETRIEVAL_MISS" if weak else "KNOWLEDGE_ABSENT"

        return "RETRIEVAL_MISS"

    def _probe_weak_hits(self, kb_id: str, query: str) -> bool:
        try:
            collection = get_collection(kb_id)
            emb = self.embed_svc.embed_query(query)
            results = collection.query(query_embeddings=[emb], n_results=5)
            if not results or not results.get("distances") or not results["distances"][0]:
                return False
            for dist in results["distances"][0]:
                if 0.7 * (1 - dist) >= WEAK_HIT_SCORE:
                    return True
        except Exception:
            return False
        return False

    @staticmethod
    def _looks_like_user_fact(text: str) -> bool:
        t = text.strip()
        if len(t) < 12:
            return False
        markers = ("是", "为", "等于", "指的是", "定义为", "应该", "需要")
        return any(m in t for m in markers) and "?" not in t and "？" not in t

    @staticmethod
    def should_enqueue(
        retrieval_result: list[dict],
        answer: str,
    ) -> bool:
        if not retrieval_result:
            return True
        max_score = max((s.get("score") or 0) for s in retrieval_result)
        if max_score < ABSENT_SCORE:
            return True
        if any(p in (answer or "") for p in NO_INFO_PHRASES):
            return True
        return False

    async def create_gap(
        self,
        *,
        kb_id: str,
        query: str,
        gap_type: str,
        conversation_id: str | None = None,
        message_id: str | None = None,
        source_ref: str | None = None,
        retrieval_result: list[dict] | None = None,
        confidence: float | None = None,
    ) -> KnowledgeGap:
        if gap_type not in GAP_TYPES:
            raise ValueError(f"invalid gap_type: {gap_type}")

        status = "manual_required" if gap_type == "KNOWLEDGE_ABSENT" else "pending"
        if gap_type in ("USER_PROVIDED", "USER_CORRECTION"):
            status = "suggested"

        ref = source_ref
        if ref is None and retrieval_result:
            ref = json.dumps(
                [{"chunk_id": s.get("chunk_id"), "score": s.get("score")} for s in retrieval_result[:5]],
                ensure_ascii=False,
            )

        gap = KnowledgeGap(
            kb_id=kb_id,
            query=query,
            conversation_id=conversation_id,
            message_id=message_id,
            gap_type=gap_type,
            status=status,
            source_ref=ref,
            confidence=confidence,
        )
        self.db.add(gap)
        await self.db.commit()
        await self.db.refresh(gap)
        return gap

    async def maybe_enqueue_from_chat(
        self,
        *,
        kb_id: str,
        query: str,
        answer: str,
        sources: list[dict],
        conversation_id: str,
        message_id: str,
    ) -> KnowledgeGap | None:
        if not self.should_enqueue(sources, answer):
            return None

        gap_type = self.classify_gap(query, kb_id, sources, user_message=query)
        existing = await self.db.execute(
            select(KnowledgeGap).where(
                KnowledgeGap.kb_id == kb_id,
                KnowledgeGap.query == query,
                KnowledgeGap.status.in_(("pending", "suggested", "manual_required")),
            )
        )
        if existing.scalar_one_or_none():
            return None

        return await self.create_gap(
            kb_id=kb_id,
            query=query,
            gap_type=gap_type,
            conversation_id=conversation_id,
            message_id=message_id,
            retrieval_result=sources,
        )

    async def list_gaps(
        self,
        kb_id: str,
        *,
        gap_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[KnowledgeGap]:
        q = select(KnowledgeGap).where(KnowledgeGap.kb_id == kb_id)
        if gap_type:
            q = q.where(KnowledgeGap.gap_type == gap_type)
        if status:
            q = q.where(KnowledgeGap.status == status)
        q = q.order_by(KnowledgeGap.created_at.desc()).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def update_status(self, gap_id: str, status: str) -> KnowledgeGap | None:
        if status not in GAP_STATUSES:
            raise ValueError(f"invalid status: {status}")
        gap = await self.db.get(KnowledgeGap, gap_id)
        if not gap:
            return None
        gap.status = status
        await self.db.commit()
        await self.db.refresh(gap)
        return gap
