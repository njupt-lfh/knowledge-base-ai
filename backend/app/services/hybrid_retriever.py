"""Hybrid 检索 — Phase 2.1: Vector + FTS5 BM25 + RRF + Rerank"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.chroma_client import get_collection
from ..core.config import settings
from ..models.chunk import Chunk
from .embedding_service import EmbeddingService
from .fts_service import search_fts
from .quality_service import QualityService, blend_retrieval_score
from .rerank_service import rerank_candidates

logger = logging.getLogger(__name__)

RRF_K = 60


def reciprocal_rank_fusion(ranked_lists: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ids in ranked_lists:
        for rank, cid in enumerate(ids, start=1):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    return scores


def merge_source_lists(lists: list[list[dict[str, Any]]], *, top_k: int) -> list[dict[str, Any]]:
    """多路检索结果 RRF 融合（保留 chunk 内容与 source 标记）。"""
    ranked_ids = [[s["chunk_id"] for s in lst] for lst in lists if lst]
    if not ranked_ids:
        return []
    rrf_scores = reciprocal_rank_fusion(ranked_ids)
    by_id: dict[str, dict[str, Any]] = {}
    for lst in lists:
        for item in lst:
            cid = item["chunk_id"]
            prev = by_id.get(cid)
            if prev is None:
                by_id[cid] = dict(item)
            else:
                sources = {prev.get("source", "hybrid"), item.get("source", "hybrid")}
                prev["source"] = "+".join(sorted(sources))
                if item.get("graph_seeds"):
                    prev["graph_seeds"] = item["graph_seeds"]
    merged = []
    for cid, score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
        if cid not in by_id:
            continue
        row = by_id[cid]
        row["score"] = round(score, 6)
        row["rrf_score"] = row["score"]
        merged.append(row)
    return merged[:top_k]


def dynamic_top_k(query: str, default: int = 5) -> int:
    n = len(query.strip())
    if n < 15:
        return max(3, default - 1)
    if n > 80:
        return min(10, default + 2)
    return default


class HybridRetriever:
    def __init__(self):
        self.embed_svc = EmbeddingService()

    async def search(
        self,
        db: AsyncSession,
        kb_id: str,
        query: str,
        *,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        k = top_k or dynamic_top_k(query, getattr(settings, "RETRIEVAL_TOP_K", 5))
        vec_limit = getattr(settings, "HYBRID_VECTOR_CANDIDATES", 15)
        fts_limit = getattr(settings, "HYBRID_FTS_CANDIDATES", 15)

        vector_ids = await self._vector_search(kb_id, query, vec_limit)
        fts_hits = await search_fts(db, kb_id, query, limit=fts_limit)
        fts_ids = [cid for cid, _ in fts_hits]

        if not vector_ids and not fts_ids:
            return []

        rrf_scores = reciprocal_rank_fusion([vector_ids, fts_ids])
        candidate_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[
            : max(k * 3, 12)
        ]

        chunks = (
            (
                await db.execute(
                    select(Chunk).where(
                        Chunk.id.in_(candidate_ids),
                        Chunk.knowledge_base_id == kb_id,
                        Chunk.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        chunk_map = {c.id: c for c in chunks}

        candidates: list[dict[str, Any]] = []
        for cid in candidate_ids:
            chunk = chunk_map.get(cid)
            if not chunk:
                continue
            candidates.append(
                {
                    "chunk_id": cid,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "document_id": chunk.document_id,
                    "rrf_score": round(rrf_scores[cid], 6),
                    "score": round(rrf_scores[cid], 6),
                    "source": "hybrid",
                }
            )

        if getattr(settings, "HYBRID_RERANK_ENABLED", True):
            candidates = rerank_candidates(query, candidates, top_k=k)
        else:
            candidates = candidates[:k]

        quality_svc = QualityService(db)
        qmap = await quality_svc.get_scores_map([c["chunk_id"] for c in candidates])
        for c in candidates:
            q = qmap.get(c["chunk_id"], 0.5)
            c["quality_score"] = q
            c["score"] = blend_retrieval_score(c["score"], q)

        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:k]

    async def vector_only_search(
        self,
        db: AsyncSession,
        kb_id: str,
        query: str,
        *,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """纯向量检索基线（Phase 3 多跳对比用）。"""
        k = top_k or dynamic_top_k(query, getattr(settings, "RETRIEVAL_TOP_K", 5))
        vec_limit = max(k * 3, 15)
        vector_ids = await self._vector_search(kb_id, query, vec_limit)
        if not vector_ids:
            return []

        chunks = (
            (
                await db.execute(
                    select(Chunk).where(
                        Chunk.id.in_(vector_ids),
                        Chunk.knowledge_base_id == kb_id,
                        Chunk.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        chunk_map = {c.id: c for c in chunks}

        sources: list[dict[str, Any]] = []
        for rank, cid in enumerate(vector_ids, start=1):
            chunk = chunk_map.get(cid)
            if not chunk:
                continue
            score = round(1.0 / rank, 6)
            sources.append(
                {
                    "chunk_id": cid,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "document_id": chunk.document_id,
                    "score": score,
                    "source": "vector",
                }
            )
        return sources[:k]

    async def _vector_search(self, kb_id: str, query: str, limit: int) -> list[str]:
        try:
            collection = get_collection(kb_id)
            emb = self.embed_svc.embed_query(query)
            results = collection.query(query_embeddings=[emb], n_results=limit)
        except Exception as e:
            logger.warning("vector search failed: %s", e)
            return []

        if not results or not results.get("ids") or not results["ids"][0]:
            return []

        ids: list[str] = []
        for i, cid in enumerate(results["ids"][0]):
            dist = results["distances"][0][i] if results.get("distances") else 1.0
            if 0.7 * (1 - dist) > 0.15:
                ids.append(cid)
        return ids
