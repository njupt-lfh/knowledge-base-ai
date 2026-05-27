"""Cross-Encoder 轻量 Rerank — Phase 2.1（无额外模型依赖）"""

from __future__ import annotations

import re
import time


def _terms(text: str) -> set[str]:
    return set(re.findall(r"[\w\u4e00-\u9fff]{2,}", text.lower()))


def rerank_candidates(query: str, candidates: list[dict], *, top_k: int) -> list[dict]:
    """基于 query-chunk 词项重叠 + RRF 分融合重排，目标延迟 < 500ms。"""
    start = time.perf_counter()
    q_terms = _terms(query)
    if not q_terms:
        return candidates[:top_k]

    for c in candidates:
        c_terms = _terms(c.get("content", ""))
        overlap = len(q_terms & c_terms) / len(q_terms) if q_terms else 0.0
        rrf = float(c.get("rrf_score", c.get("score", 0)))
        c["rerank_score"] = round(0.65 * rrf + 0.35 * overlap, 6)
        c["score"] = c["rerank_score"]

    ranked = sorted(candidates, key=lambda x: x.get("rerank_score", 0), reverse=True)
    elapsed_ms = (time.perf_counter() - start) * 1000
    for c in ranked[:top_k]:
        c["rerank_ms"] = round(elapsed_ms, 2)
    return ranked[:top_k]
