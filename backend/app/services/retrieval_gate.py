"""检索置信度门控（Phase 3 负例 abstention，无额外 LLM）。

职责：
    在 Hybrid/Graph 检索后、进入 CRAG 之前，对低置信且无图谱支撑的结果
    直接清空，降低负例误召回（false positive）。

在流水线中的位置：
    AgentOrchestrator._retrieve → apply_retrieval_abstention

依赖服务：
    - crag_evaluator.evaluate_sufficiency：复用词项重叠与分数评估
    - query_router.QueryRoute
"""

from __future__ import annotations

from typing import Any

from ..core.config import settings
from .crag_evaluator import (
    RRF_SCALE_SCORE_CEILING,
    _anchor_match_count,
    _anchor_terms_from_query,
    evaluate_sufficiency,
)
from .query_router import QueryRoute


def _low_quality_dominates(sources: list[dict], threshold: float = 0.30) -> bool:
    """检查 top-3 中低质量 chunk 是否占多数（>2/3）。

    用于 CE+quality 双条件拒答：即使 CE 分数高，如果 chunk 质量普遍偏低，
    说明这些 chunk 可能已被用户多次点踩或标记，不应展示。

    参数:
        sources: 检索来源列表（需含 quality_score 字段）
        threshold: 低质量阈值

    返回:
        True 表示低质量占主导，应拒答
    """
    if len(sources) < 3:
        return False
    top3 = sources[:3]
    low_count = sum(1 for s in top3 if (s.get("quality_score") or 0.5) < threshold)
    return low_count > 2  # > 2/3 of top-3


def _anchor_mismatch(
    query: str,
    sources: list[dict[str, Any]],
    *,
    anchor_overlap: float,
    min_anchor: float,
    min_anchor_matches: int,
) -> bool:
    """query 含锚点词但 sources 未充分命中 → True（near_domain 误召回信号）。"""
    anchor_q = _anchor_terms_from_query(query)
    if not anchor_q:
        return False
    required = min(min_anchor_matches, len(anchor_q))
    if _anchor_match_count(anchor_q, sources) >= required and anchor_overlap >= min_anchor:
        return False
    return True


def _near_domain_abstain(
    query: str,
    sources: list[dict[str, Any]],
    *,
    ce_top_score: float,
    ce_threshold: float,
    anchor_overlap: float,
    min_anchor: float,
    min_anchor_matches: int,
) -> bool:
    """near_domain：CE ∈ [ce_threshold, 0.45) 且 anchor 不匹配 → 应空检索。"""
    if not getattr(settings, "NEAR_DOMAIN_GATE_ENABLED", True):
        return False
    near_max = float(getattr(settings, "NEAR_DOMAIN_CE_MAX", 0.45))
    if ce_top_score >= near_max or ce_top_score < ce_threshold:
        return False
    return _anchor_mismatch(
        query,
        sources,
        anchor_overlap=anchor_overlap,
        min_anchor=min_anchor,
        min_anchor_matches=min_anchor_matches,
    )


def apply_retrieval_abstention(
    query: str,
    sources: list[dict[str, Any]],
    route: QueryRoute,
    *,
    graph_paths: list[dict[str, Any]] | None = None,
    ce_min_score: float | None = None,
    multi_hop_relaxed: bool = False,
) -> list[dict[str, Any]]:
    """低置信且无图谱支撑时返回空检索，降低负例误召回。

    参数:
        query: 用户查询
        sources: 检索来源列表
        route: 问题路由类型
        graph_paths: 图谱多跳路径（有则放宽 abstention）
        ce_min_score: CE 最低分数阈值（默认 0.35；relaxed 路径可用 0.25）

    返回:
        过滤后的来源列表（可能为空）
    """
    if not sources or route == "chitchat":
        return sources

    if not getattr(settings, "RETRIEVAL_ABSTAIN_ENABLED", True):
        return sources

    eval_result = evaluate_sufficiency(query, sources, route)
    max_score = eval_result.max_retrieval_score
    overlap = eval_result.term_overlap
    substantive_overlap = eval_result.substantive_overlap
    anchor_overlap = eval_result.anchor_overlap
    overlap_for_gate = max(overlap, substantive_overlap, anchor_overlap)

    min_score = getattr(settings, "RETRIEVAL_ABSTAIN_MIN_SCORE", 0.06)
    min_overlap = getattr(settings, "RETRIEVAL_ABSTAIN_MIN_OVERLAP", 0.12)
    min_substantive = getattr(settings, "RETRIEVAL_ABSTAIN_MIN_SUBSTANTIVE", 0.05)
    min_anchor = getattr(settings, "RETRIEVAL_ABSTAIN_MIN_ANCHOR", 0.20)
    min_anchor_matches = int(getattr(settings, "RETRIEVAL_ABSTAIN_MIN_ANCHOR_MATCHES", 2))

    # CE 已启用时：仅当 sources 确实经过 CE 打分时才应用 CE 规则
    ce_enabled = getattr(settings, "CROSS_ENCODER_RERANK_ENABLED", False)
    ce_threshold = ce_min_score if ce_min_score is not None else 0.35
    ce_top_score = None
    has_ce_scores = False
    if ce_enabled and sources:
        ce_scores = [s.get("cross_encoder_score", 0) or 0 for s in sources]
        has_ce_scores = any(s.get("cross_encoder_score") is not None for s in sources)
        if ce_scores:
            ce_top_score = max(ce_scores, default=0)

        # Phase 1 P0-1 fix: 仅当 sources 确实有 CE 分数时才应用 CE 阈值
        if has_ce_scores:
            # top-1 CE < threshold → unclear relevance → empty retrieval
            if ce_top_score < ce_threshold:
                return []

            # CE 对 top chunk 有足够信心 → 不触发 gate
            if ce_top_score >= 0.50:
                if _low_quality_dominates(sources):
                    return []
                return sources

            # Phase 1 P1：near_domain — CE ∈ [threshold, 0.45) 且 anchor 不匹配 → 空检索
            if _near_domain_abstain(
                query,
                sources,
                ce_top_score=ce_top_score,
                ce_threshold=ce_threshold,
                anchor_overlap=anchor_overlap,
                min_anchor=min_anchor,
                min_anchor_matches=min_anchor_matches,
            ):
                return []

    # Phase 1: quality 双条件 — top-3 中 quality < 0.30 占比 > 2/3 → 空检索
    if _low_quality_dominates(sources):
        return []

    # 有图谱路径支撑时放宽阈值
    has_graph = bool(graph_paths) or any("graph" in str(s.get("source", "")) for s in sources)

    # Phase 3 G-L4: 图支撑不盲目 bypass CE — CE 分过低时图路径也不放行
    if has_graph and max_score >= min_score * 0.6:
        if has_ce_scores and ce_top_score is not None:
            if ce_top_score < ce_threshold:
                return []  # CE 低 → 图路径也拒
        return sources

    # 书名号/锚点 query：核心实体词命中不足 → 空检索
    # multi_hop 双路合并：允许 A/B 各落在不同 chunk，不要求单 chunk 双命中
    anchor_q = _anchor_terms_from_query(query)
    if anchor_q and not multi_hop_relaxed:
        required_matches = min(min_anchor_matches, len(anchor_q))
        if _anchor_match_count(anchor_q, sources) < required_matches:
            return []
        if anchor_overlap < min_anchor:
            return []

    # RRF 尺度：实质词面无锚点 → 视为误召回
    if substantive_overlap < min_substantive and max_score < RRF_SCALE_SCORE_CEILING:
        return []

    # RRF 尺度（分数约 0.01–0.17）：词项重叠是唯一可靠判别器
    if overlap_for_gate < min_overlap * 0.75 and max_score < 0.18:
        return []

    if max_score < min_score and overlap_for_gate < min_overlap:
        return []

    if route == "factual" and max_score < min_score * 0.85 and overlap_for_gate < min_overlap * 0.8:
        return []

    return sources
