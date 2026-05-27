"""CRAG-lite 充分性评估 — Phase 2.2（无额外 LLM 调用）"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..core.config import settings
from .query_router import QueryRoute


@dataclass
class SufficiencyResult:
    sufficient: bool
    score: float
    max_retrieval_score: float
    term_overlap: float
    reason: str


def _terms(text: str) -> set[str]:
    return set(re.findall(r"[\w\u4e00-\u9fff]{2,}", (text or "").lower()))


def evaluate_sufficiency(
    query: str,
    sources: list[dict[str, Any]],
    route: QueryRoute,
) -> SufficiencyResult:
    min_score = getattr(settings, "CRAG_MIN_SCORE", 0.22)
    min_overlap = getattr(settings, "CRAG_MIN_OVERLAP", 0.12)

    if route == "chitchat":
        return SufficiencyResult(True, 1.0, 0.0, 0.0, "chitchat_skip")

    if not sources:
        return SufficiencyResult(False, 0.0, 0.0, 0.0, "empty_sources")

    q_terms = _terms(query)
    overlaps: list[float] = []
    scores = [float(s.get("score") or 0) for s in sources]
    max_score = max(scores) if scores else 0.0

    for s in sources:
        c_terms = _terms(s.get("content", ""))
        if q_terms:
            overlaps.append(len(q_terms & c_terms) / len(q_terms))
        else:
            overlaps.append(0.0)

    term_overlap = max(overlaps) if overlaps else 0.0

    if route == "relational":
        min_score *= 0.85
        min_overlap *= 0.85
    elif route == "comprehensive":
        min_score *= 0.9

    combined = 0.55 * min(1.0, max_score / 0.5) + 0.45 * min(1.0, term_overlap / 0.35)
    sufficient = max_score >= min_score and (term_overlap >= min_overlap or max_score >= min_score * 1.8)

    reason = "ok" if sufficient else f"weak(max={max_score:.3f},overlap={term_overlap:.3f})"
    return SufficiencyResult(sufficient, round(combined, 4), max_score, round(term_overlap, 4), reason)
