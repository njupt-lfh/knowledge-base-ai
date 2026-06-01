"""CRAG-lite 检索充分性评估（Phase 2.2，无额外 LLM 调用）。

职责：
    基于检索分数与 query-chunk 词项重叠，判断当前来源是否足以支撑回答，
    驱动 Agent 第二轮重试或拒答（abstention）。

在流水线中的位置：
    AgentOrchestrator.run → evaluate_sufficiency
    retrieval_gate.apply_retrieval_abstention → evaluate_sufficiency
    sim_rag_service.evaluate_sim_sufficiency → evaluate_sufficiency

依赖服务：
    - query_router.QueryRoute：不同路由类型使用不同阈值
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..core.config import settings
from .query_router import QueryRoute


@dataclass
class SufficiencyResult:
    """CRAG 充分性评估结果。"""

    sufficient: bool
    score: float
    max_retrieval_score: float
    term_overlap: float
    reason: str


def _terms(text: str) -> set[str]:
    """从文本提取检索用词项（拉丁词 + 中文 1-2 字切分）。

    参数:
        text: 待分词文本

    返回:
        词项集合
    """
    t = (text or "").lower()
    # 拉丁字母词（ASCII）
    latin = set(re.findall(r"(?a)\w{2,}", t))
    # 中文：按标点切分，避免贪婪匹配吞掉整句
    cjk = set()
    for seg in re.split(
        r"[\uff0c\u3002\uff1b\u3001\uff01\uff1f\s\u00b7\u2026\u2014,.;!?\n\r\t\u4e0e\u548c\u53ca\u6216\u7684]+",
        t,
    ):
        cjk.update(re.findall(r"[\u4e00-\u9fff]{1,2}", seg))
    return latin | cjk


# Hybrid RRF + 轻量 rerank 的分值通常 < 0.15，与 0.2+ 的绝对阈值不可直接比较
RRF_SCALE_SCORE_CEILING = 0.15


def evaluate_sufficiency(
    query: str,
    sources: list[dict[str, Any]],
    route: QueryRoute,
) -> SufficiencyResult:
    """评估检索结果是否充分（CRAG-lite 核心逻辑）。

    参数:
        query: 用户原始查询
        sources: 检索来源列表
        route: QueryRouter 判定的问题类型

    返回:
        SufficiencyResult，含 sufficient 布尔与综合 score
    """
    min_score = getattr(settings, "CRAG_MIN_SCORE", 0.22)
    min_overlap = getattr(settings, "CRAG_MIN_OVERLAP", 0.12)

    # 寒暄类跳过检索，视为充分
    if route == "chitchat":
        return SufficiencyResult(True, 1.0, 0.0, 0.0, "chitchat_skip")

    if not sources:
        return SufficiencyResult(False, 0.0, 0.0, 0.0, "empty_sources")

    q_terms = _terms(query)
    overlaps: list[float] = []
    scores = [float(s.get("score") or 0) for s in sources]
    max_score = max(scores) if scores else 0.0

    # 计算 query 与每个 chunk 的词项重叠率
    for s in sources:
        c_terms = _terms(s.get("content", ""))
        if q_terms:
            overlaps.append(len(q_terms & c_terms) / len(q_terms))
        else:
            overlaps.append(0.0)

    term_overlap = max(overlaps) if overlaps else 0.0

    # 关系型/综合型问题放宽阈值
    if route == "relational":
        min_score *= 0.85
        min_overlap *= 0.85
    elif route == "comprehensive":
        min_score *= 0.9

    combined = 0.55 * min(1.0, max_score / 0.5) + 0.45 * min(1.0, term_overlap / 0.35)

    if max_score < RRF_SCALE_SCORE_CEILING:
        # RRF 尺度：以词面重叠为主，避免「图谱/检索有命中但分低」被误拒答
        sufficient = max_score > 0 and term_overlap >= min_overlap
    else:
        sufficient = max_score >= min_score and (
            term_overlap >= min_overlap or max_score >= min_score * 1.8
        )

    reason = "ok" if sufficient else f"weak(max={max_score:.3f},overlap={term_overlap:.3f})"
    return SufficiencyResult(
        sufficient, round(combined, 4), max_score, round(term_overlap, 4), reason
    )
