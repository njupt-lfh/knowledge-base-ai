"""入库质量门禁 — Phase 1.4：去重 + 冲突检测"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.chroma_client import get_collection
from ..models.chunk import Chunk
from ..models.knowledge_conflict import KnowledgeConflict
from ..services.embedding_service import EmbeddingService
from ..services.llm_service import LLMService

logger = logging.getLogger(__name__)

TOP_K = 3
# 归一化向量：cos>0.92 → L2<0.4；cos≥0.75 → L2<√0.5
DUPLICATE_MAX_DISTANCE = 0.4
CONFLICT_MAX_DISTANCE = 0.7071067811865476


def distance_to_similarity(distance: float) -> float:
    return round(max(0.0, 1.0 - distance * distance / 2.0), 4)


@dataclass
class GateCandidate:
    chunk_id: str
    distance: float
    similarity: float
    content_preview: str


@dataclass
class ChunkGateResult:
    status: str  # allow | duplicate | conflict
    duplicate_of: str | None = None
    similarity: float | None = None
    conflict_candidates: list[GateCandidate] = field(default_factory=list)
    llm_calls: int = 0


@dataclass
class IngestStats:
    allowed: int = 0
    duplicates: int = 0
    conflicts: int = 0
    llm_calls: int = 0


class IngestionGateService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.embed_svc = EmbeddingService()
        self.llm_svc = LLMService()

    async def check_content(
        self,
        kb_id: str,
        content: str,
        *,
        exclude_chunk_ids: set[str] | None = None,
    ) -> ChunkGateResult:
        exclude_chunk_ids = exclude_chunk_ids or set()
        text = content.strip()
        if not text:
            return ChunkGateResult(status="allow")

        candidates = await self._find_similar(kb_id, text, exclude_chunk_ids)
        if not candidates:
            return ChunkGateResult(status="allow")

        best = candidates[0]
        if best.distance < DUPLICATE_MAX_DISTANCE:
            return ChunkGateResult(
                status="duplicate",
                duplicate_of=best.chunk_id,
                similarity=best.similarity,
            )

        conflict_zone = [c for c in candidates if c.distance < CONFLICT_MAX_DISTANCE]
        if not conflict_zone:
            return ChunkGateResult(status="allow")

        llm_calls = 0
        for cand in conflict_zone[:TOP_K]:
            llm_calls += 1
            if await self._llm_has_conflict(cand.content_preview, text):
                logger.info(
                    "ingestion_gate: conflict kb=%s existing=%s sim=%.3f llm_calls=%d",
                    kb_id,
                    cand.chunk_id,
                    cand.similarity,
                    llm_calls,
                )
                return ChunkGateResult(
                    status="conflict",
                    conflict_candidates=conflict_zone,
                    llm_calls=llm_calls,
                )

        logger.info("ingestion_gate: no conflict after %d LLM checks kb=%s", llm_calls, kb_id)
        return ChunkGateResult(status="allow", llm_calls=llm_calls)

    async def _find_similar(
        self, kb_id: str, content: str, exclude_chunk_ids: set[str]
    ) -> list[GateCandidate]:
        try:
            collection = get_collection(kb_id)
            emb = self.embed_svc.embed_query(content[:2000])
            results = collection.query(
                query_embeddings=[emb],
                n_results=TOP_K + len(exclude_chunk_ids),
                include=["distances", "documents"],
            )
        except Exception:
            return []

        if not results or not results.get("ids") or not results["ids"][0]:
            return []

        out: list[GateCandidate] = []
        for i, cid in enumerate(results["ids"][0]):
            if cid in exclude_chunk_ids:
                continue
            dist = results["distances"][0][i] if results.get("distances") else 1.0
            doc = results["documents"][0][i] if results.get("documents") else ""
            out.append(
                GateCandidate(
                    chunk_id=cid,
                    distance=dist,
                    similarity=distance_to_similarity(dist),
                    content_preview=(doc or "")[:500],
                )
            )
            if len(out) >= TOP_K:
                break
        return sorted(out, key=lambda c: c.distance)

    async def _llm_has_conflict(self, existing: str, new: str) -> bool:
        if self.llm_svc.mock_mode:
            return False

        prompt = (
            "判断以下两段知识是否语义矛盾（互相否定或给出不可共存的事实）。\n"
            f"【已有】\n{existing[:1500]}\n\n"
            f"【待入库】\n{new[:1500]}\n\n"
            '仅回复 JSON：{"conflict": true或false, "reason": "简短说明"}'
        )
        try:
            raw = await self.llm_svc.chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=256,
            )
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(raw[start:end])
                return bool(data.get("conflict"))
        except Exception as e:
            logger.warning("ingestion_gate LLM conflict check failed: %s", e)
        return False

    async def record_conflict(
        self,
        kb_id: str,
        new_content: str,
        candidate: GateCandidate,
        *,
        source_document_id: str | None = None,
        llm_reason: str | None = None,
    ) -> KnowledgeConflict:
        row = KnowledgeConflict(
            id=str(uuid.uuid4()),
            knowledge_base_id=kb_id,
            existing_chunk_id=candidate.chunk_id,
            new_content=new_content,
            similarity=candidate.similarity,
            status="pending",
            llm_reason=llm_reason,
            source_document_id=source_document_id,
        )
        self.db.add(row)
        return row


async def ingest_text_chunks(
    db: AsyncSession,
    kb_id: str,
    doc_id: str,
    texts: list[str],
    *,
    exclude_chunk_ids: set[str] | None = None,
    start_chunk_index: int = 0,
) -> tuple[list[Chunk], IngestStats]:
    """分块文本经门禁后写入 DB（不含 Chroma，由调用方批量写入向量）。"""
    gate = IngestionGateService(db)
    exclude = exclude_chunk_ids or set()
    stats = IngestStats()
    records: list[Chunk] = []
    next_index = start_chunk_index

    for text in texts:
        result = await gate.check_content(kb_id, text, exclude_chunk_ids=exclude)
        stats.llm_calls += result.llm_calls

        if result.status == "duplicate":
            stats.duplicates += 1
            logger.info(
                "ingestion_gate: skip duplicate kb=%s doc=%s sim=%s existing=%s",
                kb_id,
                doc_id,
                result.similarity,
                result.duplicate_of,
            )
            continue

        if result.status == "conflict" and result.conflict_candidates:
            stats.conflicts += 1
            cand = result.conflict_candidates[0]
            await gate.record_conflict(
                kb_id,
                text,
                cand,
                source_document_id=doc_id,
                llm_reason="LLM 检测到语义冲突",
            )
            continue

        stats.allowed += 1
        records.append(
            Chunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                knowledge_base_id=kb_id,
                content=text,
                chunk_index=next_index,
                char_count=len(text),
            )
        )
        next_index += 1

    return records, stats
