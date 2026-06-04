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
    substantive_overlap: float = 0.0
    anchor_overlap: float = 0.0


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


# 评测/用户套话：参与 abstention 重叠计算会抬高负例误召回（如「本知识库」）
_ABSTENTION_STOP_TERMS = frozenset(
    {
        "本知",
        "知识",
        "识库",
        "请介",
        "介绍",
        "详细",
        "记录",
        "是什么",
        "根据",
        "要点",
        "解释",
        "综合",
        "说明",
        "章节",
        "内容",
        "相关",
        "有何",
        "关联",
        "关于",
    }
)


def _substantive_query_terms(query: str) -> set[str]:
    """提取 query 中的实质词项（剔除模板套话），供 abstention / CRAG 重叠判定。"""
    return {t for t in _terms(query) if t not in _ABSTENTION_STOP_TERMS}


def _anchor_terms_from_query(query: str) -> set[str]:
    """从书名号/「」或「本知识库中 … 章节」提取核心锚点词（负例与高噪声 query）。"""
    anchors: set[str] = set()
    for match in re.finditer(r"[「『]([^」』]+)[」』]", query):
        anchors |= _substantive_query_terms(match.group(1))
    tail = re.search(r"本知识库中\s*(.+?)(?:章节|的详细|$)", query)
    if tail:
        anchors |= _substantive_query_terms(tail.group(1))
    return anchors


def _max_term_overlap(query_terms: set[str], sources: list[dict[str, Any]]) -> float:
    """query 词项与 sources 的最大词项重叠率。"""
    if not query_terms or not sources:
        return 0.0
    overlaps: list[float] = []
    for s in sources:
        c_terms = _terms(s.get("content", ""))
        overlaps.append(len(query_terms & c_terms) / len(query_terms))
    return max(overlaps) if overlaps else 0.0


def _anchor_match_count(anchor_q: set[str], sources: list[dict[str, Any]]) -> int:
    """锚点词项与单 chunk 的最大命中个数（防「ReAct→react」「18 岁→18」单字误匹配）。"""
    if not anchor_q or not sources:
        return 0
    best = 0
    for s in sources:
        c_terms = _terms(s.get("content", ""))
        best = max(best, len(anchor_q & c_terms))
    return best


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
    min_score = getattr(settings, "CRAG_MIN_SCORE", 0.06)
    min_overlap = getattr(settings, "CRAG_MIN_OVERLAP", 0.10)

    # 寒暄类跳过检索，视为充分
    if route == "chitchat":
        return SufficiencyResult(True, 1.0, 0.0, 0.0, "chitchat_skip")

    if not sources:
        return SufficiencyResult(False, 0.0, 0.0, 0.0, "empty_sources")

    q_terms = _terms(query)
    substantive_q = _substantive_query_terms(query) or q_terms
    anchor_q = _anchor_terms_from_query(query)
    overlaps: list[float] = []
    substantive_overlaps: list[float] = []
    scores = [float(s.get("score") or 0) for s in sources]
    max_score = max(scores) if scores else 0.0

    # 计算 query 与每个 chunk 的词项重叠率（含实质词项口径）
    for s in sources:
        c_terms = _terms(s.get("content", ""))
        if q_terms:
            overlaps.append(len(q_terms & c_terms) / len(q_terms))
        else:
            overlaps.append(0.0)
        if substantive_q:
            substantive_overlaps.append(len(substantive_q & c_terms) / len(substantive_q))
        else:
            substantive_overlaps.append(0.0)

    term_overlap = max(overlaps) if overlaps else 0.0
    substantive_overlap = max(substantive_overlaps) if substantive_overlaps else 0.0
    anchor_overlap = _max_term_overlap(anchor_q, sources) if anchor_q else 0.0
    overlap_for_decision = max(term_overlap, substantive_overlap, anchor_overlap)

    # 关系型/综合型问题放宽阈值
    if route == "relational":
        min_score *= 0.85
        min_overlap *= 0.85
    elif route == "comprehensive":
        min_score *= 0.9

    combined = 0.55 * min(1.0, max_score / 0.5) + 0.45 * min(1.0, overlap_for_decision / 0.35)

    if max_score < RRF_SCALE_SCORE_CEILING:
        # RRF 尺度：以实质词面重叠为主，避免「图谱/检索有命中但分低」被误拒答
        sufficient = max_score > 0 and overlap_for_decision >= min_overlap
    else:
        sufficient = max_score >= min_score and (
            overlap_for_decision >= min_overlap or max_score >= min_score * 1.8
        )

    reason = (
        "ok"
        if sufficient
        else f"weak(max={max_score:.3f},overlap={overlap_for_decision:.3f},anchor={anchor_overlap:.3f})"
    )
    return SufficiencyResult(
        sufficient,
        round(combined, 4),
        max_score,
        round(term_overlap, 4),
        reason,
        round(substantive_overlap, 4),
        round(anchor_overlap, 4),
    )
