"""SIM-RAG 多轮检索 + 子问题覆盖度 Critic — Phase 4.3（无额外 LLM，严格子查询预算）"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from .crag_evaluator import SufficiencyResult, evaluate_sufficiency
from .hybrid_retriever import HybridRetriever, merge_source_lists
from .query_router import QueryRoute
from .retrieval_gate import apply_retrieval_abstention

_SUB_SPLIT = re.compile(r"[？?；;]\s*")
_SUB_JOINERS = ("以及", "并且", "还有", "另外", "同时")


@dataclass
class SimRagResult:
    sources: list[dict[str, Any]]
    sub_queries: list[str]
    coverage: float
    sufficiency: SufficiencyResult
    graph_paths: list[dict[str, Any]] = field(default_factory=list)
    rounds_used: int = 1


def should_use_sim_rag(route: QueryRoute, query: str) -> bool:
    if not getattr(settings, "SIM_RAG_ENABLED", True):
        return False
    if route == "chitchat":
        return False
    if len(decompose_sub_queries(query)) >= 2:
        return True
    if route == "comprehensive":
        return True
    text = (query or "").strip()
    if len(text) >= 28 and any(j in text for j in _SUB_JOINERS):
        return True
    return False


def decompose_sub_queries(query: str, *, max_sub: int | None = None) -> list[str]:
    """规则拆分子问题（不消耗 LLM token）。"""
    max_sub = max_sub or getattr(settings, "SIM_RAG_MAX_SUB_QUERIES", 3)
    text = (query or "").strip()
    if not text:
        return []

    parts: list[str] = []
    for seg in _SUB_SPLIT.split(text):
        seg = seg.strip()
        if len(seg) >= 4:
            parts.append(seg)

    if len(parts) < 2:
        for joiner in _SUB_JOINERS:
            if joiner in text:
                chunks = [c.strip() for c in text.split(joiner) if len(c.strip()) >= 4]
                if len(chunks) >= 2:
                    parts = chunks
                    break

    if len(parts) < 2:
        return [text]

    deduped: list[str] = []
    seen: set[str] = set()
    for p in parts:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(p)
        if len(deduped) >= max_sub:
            break
    return deduped or [text]


def _term_overlap(query: str, content: str) -> float:
    q_terms = set(re.findall(r"[\w\u4e00-\u9fff]{2,}", (query or "").lower()))
    if not q_terms:
        return 0.0
    c_terms = set(re.findall(r"[\w\u4e00-\u9fff]{2,}", (content or "").lower()))
    return len(q_terms & c_terms) / len(q_terms)


def evaluate_subquery_coverage(sub_queries: list[str], sources: list[dict[str, Any]]) -> float:
    """每个子问题是否至少有一条来源覆盖。"""
    if not sub_queries:
        return 0.0
    min_overlap = getattr(settings, "SIM_RAG_SUBQUERY_MIN_OVERLAP", 0.15)
    hit = 0
    for sq in sub_queries:
        best = 0.0
        for s in sources:
            best = max(best, _term_overlap(sq, s.get("content", "")))
        if best >= min_overlap:
            hit += 1
    return round(hit / len(sub_queries), 4)


def evaluate_sim_sufficiency(
    query: str,
    sources: list[dict[str, Any]],
    route: QueryRoute,
    sub_queries: list[str],
) -> SufficiencyResult:
    base = evaluate_sufficiency(query, sources, route)
    coverage = evaluate_subquery_coverage(sub_queries, sources)
    min_cov = getattr(settings, "SIM_RAG_MIN_COVERAGE", 0.5)

    if len(sub_queries) <= 1:
        return base

    sufficient = base.sufficient and coverage >= min_cov
    combined_score = round(0.6 * base.score + 0.4 * coverage, 4)
    reason = base.reason if sufficient else f"low_coverage({coverage:.2f}<{min_cov})"
    return SufficiencyResult(
        sufficient=sufficient,
        score=combined_score,
        max_retrieval_score=base.max_retrieval_score,
        term_overlap=base.term_overlap,
        reason=reason,
    )


async def sim_rag_retrieve(
    db: AsyncSession,
    kb_id: str,
    query: str,
    *,
    route: QueryRoute,
    hybrid: HybridRetriever,
    retrieve_fn,
    top_k: int,
) -> SimRagResult | None:
    """
    多子查询检索并融合。retrieve_fn 签名同 AgentOrchestrator._retrieve。
    仅当可拆成 2+ 子问题时启用；否则返回 None 由调用方走常规定径。
    """
    sub_queries = decompose_sub_queries(query)
    if len(sub_queries) < 2:
        return None

    per_k = max(3, top_k // len(sub_queries) + 1)
    per_k = min(per_k, 8)
    batch_sources: list[list[dict[str, Any]]] = []
    graph_paths: list[dict[str, Any]] = []
    seen_path_keys: set[str] = set()

    for sq in sub_queries:
        sources, paths = await retrieve_fn(db, kb_id, sq, route=route, top_k=per_k)
        batch_sources.append(sources)
        for p in paths or []:
            key = str(p)
            if key not in seen_path_keys:
                seen_path_keys.add(key)
                graph_paths.append(p)

    merged = merge_source_lists(batch_sources, top_k=min(top_k + len(sub_queries), 15))
    if len(sub_queries) < 2:
        merged = apply_retrieval_abstention(query, merged, route, graph_paths=graph_paths)
    coverage = evaluate_subquery_coverage(sub_queries, merged)
    sufficiency = evaluate_sim_sufficiency(query, merged, route, sub_queries)

    return SimRagResult(
        sources=merged,
        sub_queries=sub_queries,
        coverage=coverage,
        sufficiency=sufficiency,
        graph_paths=graph_paths,
        rounds_used=1,
    )
