"""检索后硬过滤与同文档去重（Week 1 C2）。

职责：
    Cross-Encoder 分数低于阈值的 chunk 丢弃；同 document_id 最多保留 N 条。
"""

from __future__ import annotations

from typing import Any

from ..core.config import settings
from .cross_encoder_rerank_service import normalize_rerank_score


def _candidate_score(c: dict[str, Any]) -> float:
    if c.get("cross_encoder_score") is not None:
        return float(c["cross_encoder_score"])
    if c.get("cross_encoder_raw") is not None:
        return normalize_rerank_score(float(c["cross_encoder_raw"]))
    return float(c.get("rerank_score") or c.get("score") or 0)


def apply_post_retrieval_filter(
    candidates: list[dict[str, Any]],
    *,
    min_score: float | None = None,
    max_per_document: int | None = None,
    use_cross_encoder_threshold: bool | None = None,
    allow_soft_fallback: bool = True,
) -> list[dict[str, Any]]:
    """硬过滤 + 同文档 MMR 简化去重。

    参数:
        candidates: 已重排的候选列表
        min_score: Cross-Encoder 归一化分数阈值
        max_per_document: 同 document_id 最多保留条数
        use_cross_encoder_threshold: 是否启用分数阈值（仅 CE 启用时默认 True）
        allow_soft_fallback: 全滤时是否保留 top-1（Phase 1：relational/negative 应关闭）

    返回:
        过滤后的列表（可能为空）
    """
    if not candidates:
        return []

    ce_enabled = getattr(settings, "CROSS_ENCODER_RERANK_ENABLED", False)
    has_ce_scores = any(c.get("cross_encoder_score") is not None for c in candidates)
    apply_threshold = (
        use_cross_encoder_threshold
        if use_cross_encoder_threshold is not None
        else (ce_enabled and has_ce_scores)
    )
    threshold = min_score if min_score is not None else getattr(
        settings, "POST_RETRIEVAL_MIN_SCORE", 0.35
    )
    max_doc = max_per_document if max_per_document is not None else getattr(
        settings, "POST_RETRIEVAL_MAX_PER_DOCUMENT", 2
    )

    filtered: list[dict[str, Any]] = []
    for c in candidates:
        if apply_threshold and has_ce_scores:
            if _candidate_score(c) < threshold:
                continue
        filtered.append(c)

    # 阈值过严导致全灭时，保留重排第一名（可关闭，Phase 1：relational/negative 关闭）
    if not filtered and has_ce_scores and allow_soft_fallback:
        best = max(candidates, key=_candidate_score)
        filtered = [best]

    doc_counts: dict[str, int] = {}
    deduped: list[dict[str, Any]] = []
    for c in filtered:
        doc_id = str(c.get("document_id") or "")
        if doc_id:
            count = doc_counts.get(doc_id, 0)
            if count >= max_doc:
                continue
            doc_counts[doc_id] = count + 1
        deduped.append(c)

    return deduped
