"""冷知识治理 — Phase 1.3"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.chroma_client import get_collection
from ..models.chunk import Chunk
from ..models.chunk_quality import ChunkQuality
from ..services.chunk_service import ChunkService
from ..services.embedding_service import EmbeddingService
from ..services.quality_service import QualityService
from ..services.stats_service import cold_knowledge_count

COLD_DAYS = 90
DUPLICATE_SCAN_LIMIT = 40
# 归一化向量下 L2 距离 < 0.4 约等于余弦相似度 > 0.92
DUPLICATE_MAX_DISTANCE = 0.4

SUGGESTION_TYPES = (
    "duplicate",
    "cold_stale",
    "high_quality_zero_hit",
    "low_quality",
    "archive_candidate",
)

ACTION_ARCHIVE = "archive"
ACTION_DEACTIVATE = "deactivate"
ACTION_BOOST_FAQ = "boost_faq"


class GovernanceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.embed_svc = EmbeddingService()

    async def scan_suggestions(self, kb_id: str, *, scan_duplicates: bool = True) -> dict[str, Any]:
        suggestions: list[dict[str, Any]] = []
        suggestions.extend(await self._scan_cold_stale(kb_id))
        suggestions.extend(await self._scan_quality_issues(kb_id))
        if scan_duplicates:
            suggestions.extend(await self._scan_duplicates(kb_id))

        cold = await cold_knowledge_count(self.db, kb_id, COLD_DAYS)
        total = (
            await self.db.execute(
                select(func.count(Chunk.id)).where(Chunk.knowledge_base_id == kb_id)
            )
        ).scalar() or 0
        active = (
            await self.db.execute(
                select(func.count(Chunk.id)).where(
                    Chunk.knowledge_base_id == kb_id, Chunk.is_active.is_(True)
                )
            )
        ).scalar() or 0

        return {
            "kb_id": kb_id,
            "scanned_at": datetime.utcnow().isoformat(),
            "health": {
                **cold,
                "total_chunks": int(total),
                "active_chunks": int(active),
                "suggestions_count": len(suggestions),
            },
            "suggestions": suggestions,
        }

    async def _scan_cold_stale(self, kb_id: str) -> list[dict]:
        cutoff = datetime.utcnow() - timedelta(days=COLD_DAYS)
        rows = (
            (
                await self.db.execute(
                    select(Chunk)
                    .where(
                        Chunk.knowledge_base_id == kb_id,
                        Chunk.is_active.is_(True),
                        Chunk.hit_count == 0,
                        Chunk.created_at <= cutoff,
                    )
                    .order_by(Chunk.created_at)
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )

        out: list[dict] = []
        for c in rows:
            out.append(
                _suggestion(
                    stype="cold_stale",
                    title=f"冷知识块 #{c.chunk_index}",
                    description=f"创建超过 {COLD_DAYS} 天且从未被命中，建议复审或归档。",
                    chunk_ids=[c.id],
                    action=ACTION_ARCHIVE,
                    severity="warning",
                    preview=c.content[:120],
                )
            )
        return out

    async def _scan_quality_issues(self, kb_id: str) -> list[dict]:
        out: list[dict] = []
        q_rows = (
            await self.db.execute(
                select(ChunkQuality, Chunk)
                .join(Chunk, Chunk.id == ChunkQuality.chunk_id)
                .where(Chunk.knowledge_base_id == kb_id, Chunk.is_active.is_(True))
            )
        ).all()

        for q, chunk in q_rows:
            if q.needs_review and (chunk.hit_count or 0) > 0:
                out.append(
                    _suggestion(
                        stype="low_quality",
                        title=f"低质量待复审 #{chunk.chunk_index}",
                        description=f"质量分 {q.quality_score}，点踩 {q.dislike_count} 次。",
                        chunk_ids=[chunk.id],
                        action=ACTION_DEACTIVATE,
                        severity="error",
                        preview=chunk.content[:120],
                    )
                )
            elif q.quality_score >= 0.65 and (chunk.hit_count or 0) == 0:
                out.append(
                    _suggestion(
                        stype="high_quality_zero_hit",
                        title=f"高质量零命中 #{chunk.chunk_index}",
                        description="内容质量较好但从未被检索命中，可生成 FAQ 摘要提升曝光。",
                        chunk_ids=[chunk.id],
                        action=ACTION_BOOST_FAQ,
                        severity="info",
                        preview=chunk.content[:120],
                    )
                )
            elif q.quality_score < 0.25 and (chunk.hit_count or 0) == 0:
                out.append(
                    _suggestion(
                        stype="archive_candidate",
                        title=f"建议归档 #{chunk.chunk_index}",
                        description="低质量且零命中，可能为无用内容。",
                        chunk_ids=[chunk.id],
                        action=ACTION_ARCHIVE,
                        severity="warning",
                        preview=chunk.content[:120],
                    )
                )
        return out

    async def _scan_duplicates(self, kb_id: str) -> list[dict]:
        rows = (
            (
                await self.db.execute(
                    select(Chunk)
                    .where(Chunk.knowledge_base_id == kb_id, Chunk.is_active.is_(True))
                    .order_by(Chunk.created_at.desc())
                    .limit(DUPLICATE_SCAN_LIMIT)
                )
            )
            .scalars()
            .all()
        )

        out: list[dict] = []
        seen_pairs: set[frozenset[str]] = set()

        try:
            collection = get_collection(kb_id)
        except Exception:
            return out

        for chunk in rows:
            try:
                emb = self.embed_svc.embed_query(chunk.content[:2000])
                results = collection.query(
                    query_embeddings=[emb],
                    n_results=3,
                    include=["distances", "documents", "metadatas"],
                )
            except Exception:
                continue

            if not results or not results.get("ids") or not results["ids"][0]:
                continue

            for i, other_id in enumerate(results["ids"][0]):
                if other_id == chunk.id:
                    continue
                dist = results["distances"][0][i] if results.get("distances") else 1.0
                if dist > DUPLICATE_MAX_DISTANCE:
                    continue
                pair = frozenset({chunk.id, other_id})
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                other_doc = results["documents"][0][i][:80] if results.get("documents") else ""
                sim = round(max(0.0, 1.0 - dist), 4)
                out.append(
                    _suggestion(
                        stype="duplicate",
                        title="疑似重复知识块",
                        description=f"与块 {other_id[:8]}… 高度相似（距离 {dist:.3f}，约 {sim}）。建议合并。",
                        chunk_ids=[chunk.id, other_id],
                        action="merge",
                        severity="warning",
                        preview=f"{chunk.content[:60]} … / {other_doc}",
                    )
                )
                break
        return out

    async def apply_action(self, kb_id: str, action: str, chunk_ids: list[str]) -> dict[str, Any]:
        if not chunk_ids:
            raise ValueError("chunk_ids required")

        chunk_svc = ChunkService(self.db)
        quality_svc = QualityService(self.db)
        applied = 0
        details: list[str] = []

        for cid in chunk_ids:
            chunk = await self.db.get(Chunk, cid)
            if not chunk or chunk.knowledge_base_id != kb_id:
                continue

            if action in (ACTION_ARCHIVE, ACTION_DEACTIVATE):
                if chunk.is_active:
                    await chunk_svc.toggle_status(cid, False)
                    applied += 1
                    details.append(f"{cid}: 已禁用/归档")
            elif action == ACTION_BOOST_FAQ:
                q = await quality_svc.get_or_create(cid)
                q.quality_score = min(1.0, (q.quality_score or 0.5) + 0.15)
                q.needs_review = False
                await self.db.commit()
                applied += 1
                details.append(f"{cid}: 质量分提升至 {q.quality_score}")
            elif action == "merge":
                details.append(f"{cid}: 合并需人工处理，请在知识块列表中编辑后禁用重复项")
            else:
                raise ValueError(f"unknown action: {action}")

        return {"action": action, "applied": applied, "details": details}


def _suggestion(
    *,
    stype: str,
    title: str,
    description: str,
    chunk_ids: list[str],
    action: str,
    severity: str,
    preview: str,
) -> dict[str, Any]:
    return {
        "id": f"{stype}:{uuid.uuid4().hex[:12]}",
        "type": stype,
        "title": title,
        "description": description,
        "chunk_ids": chunk_ids,
        "recommended_action": action,
        "severity": severity,
        "content_preview": preview,
    }
