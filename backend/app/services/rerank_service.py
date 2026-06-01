"""Cross-Encoder 轻量 Rerank（Phase 2.1，无额外模型依赖）。

职责：
    在 Hybrid RRF 候选池上，基于 query-chunk 词项重叠与 RRF 分线性融合重排，
    目标延迟 < 500ms，不引入外部 Cross-Encoder 模型。

在流水线中的位置：
    HybridRetriever.search → rerank_candidates

依赖：无（纯本地计算）
"""

from __future__ import annotations

import re
import time


def _terms(text: str) -> set[str]:
    """提取检索用词项（与 crag_evaluator 一致的分词策略）。

    参数:
        text: 待分词文本

    返回:
        词项集合
    """
    t = text.lower()
    latin = set(re.findall(r"(?a)\w{2,}", t))
    cjk = set()
    for seg in re.split(
        r"[\uff0c\u3002\uff1b\u3001\uff01\uff1f\s\u00b7\u2026\u2014,.;!?\n\r\t\u4e0e\u548c\u53ca\u6216\u7684]+",
        t,
    ):
        cjk.update(re.findall(r"[\u4e00-\u9fff]{1,2}", seg))
    return latin | cjk


def rerank_candidates(query: str, candidates: list[dict], *, top_k: int) -> list[dict]:
    """基于 query-chunk 词项重叠 + RRF 分融合重排。

    参数:
        query: 用户查询
        candidates: RRF 候选列表（含 content、rrf_score）
        top_k: 返回条数

    返回:
        重排后的 top_k 候选，score 更新为 rerank_score
    """
    start = time.perf_counter()
    q_terms = _terms(query)
    if not q_terms:
        return candidates[:top_k]

    for c in candidates:
        c_terms = _terms(c.get("content", ""))
        overlap = len(q_terms & c_terms) / len(q_terms) if q_terms else 0.0
        rrf = float(c.get("rrf_score", c.get("score", 0)))
        # 65% RRF + 35% 词项重叠
        c["rerank_score"] = round(0.65 * rrf + 0.35 * overlap, 6)
        c["score"] = c["rerank_score"]

    ranked = sorted(candidates, key=lambda x: x.get("rerank_score", 0), reverse=True)
    elapsed_ms = (time.perf_counter() - start) * 1000
    for c in ranked[:top_k]:
        c["rerank_ms"] = round(elapsed_ms, 2)
    return ranked[:top_k]
