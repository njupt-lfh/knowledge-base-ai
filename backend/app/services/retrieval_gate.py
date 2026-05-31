"""检索置信度门控 — Phase 3 负例 abstention（无额外 LLM）"""

from __future__ import annotations

from typing import Any

from ..core.config import settings
from .crag_evaluator import evaluate_sufficiency
from .query_router import QueryRoute


def apply_retrieval_abstention(
    query: str,
    sources: list[dict[str, Any]],
    route: QueryRoute,
    *,
    graph_paths: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """低置信且无图谱支撑时返回空检索，降低负例误召回。"""
    if not sources or route == "chitchat":
        return sources

    if not getattr(settings, "RETRIEVAL_ABSTAIN_ENABLED", True):
        return sources

    eval_result = evaluate_sufficiency(query, sources, route)
    max_score = eval_result.max_retrieval_score
    overlap = eval_result.term_overlap

    min_score = getattr(settings, "RETRIEVAL_ABSTAIN_MIN_SCORE", 0.20)
    min_overlap = getattr(settings, "RETRIEVAL_ABSTAIN_MIN_OVERLAP", 0.10)

    has_graph = bool(graph_paths) or any("graph" in str(s.get("source", "")) for s in sources)

    if has_graph and max_score >= min_score * 0.6:
        return sources

    # RRF scale (scores 0.01-0.17): overlap is the only reliable discriminator
    # Negative queries have near-zero overlap → abstain
    if overlap < min_overlap * 0.75 and max_score < 0.18:
        return []

    if max_score < min_score and overlap < min_overlap:
        return []

    if route == "factual" and max_score < min_score * 0.85 and overlap < min_overlap * 0.8:
        return []

    return sources
