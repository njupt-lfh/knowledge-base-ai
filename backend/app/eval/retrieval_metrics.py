"""Chunk 级检索评测指标（与 RAGAS context_recall / context_precision 区分）。

提供标准 IR 指标（MRR、NDCG@k、Precision@k）及正负样本检索判定。
"""

from __future__ import annotations

import math
from typing import Any

# 相关性分级 → NDCG gain（v2 relevance_grades 可选）
GRADE_GAIN = {"primary": 3, "supporting": 2, "tangential": 1}


def compute_mrr(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    """Mean Reciprocal Rank：首个相关 chunk 排名的倒数。"""
    for rank, cid in enumerate(retrieved_ids, start=1):
        if cid in relevant_ids:
            return round(1.0 / rank, 4)
    return 0.0


def compute_precision_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Precision@k：前 k 个结果中相关 chunk 占比。"""
    if k <= 0:
        return 0.0
    top = retrieved_ids[:k]
    if not top:
        return 0.0
    return round(sum(1 for cid in top if cid in relevant_ids) / len(top), 4)


def compute_ndcg(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    *,
    relevance_grades: dict[str, int] | None = None,
    k: int = 5,
) -> float:
    """NDCG@k：折损累积增益（仅用于正例；负例请用 negative_reject_rate）。"""
    if not relevant_ids:
        return 0.0

    grades = relevance_grades or {}

    def _gain(cid: str) -> float:
        if cid in grades:
            return float(grades[cid])
        return 1.0 if cid in relevant_ids else 0.0

    dcg = 0.0
    for rank, cid in enumerate(retrieved_ids[:k], start=1):
        dcg += _gain(cid) / math.log2(rank + 1)

    ideal_gains = sorted(
        [_gain(rid) for rid in relevant_ids],
        reverse=True,
    )[:k]
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal_gains))
    if idcg <= 0:
        return 0.0
    return round(dcg / idcg, 4)


def _normalize_relevance_grades(raw: dict[str, str] | None) -> dict[str, int] | None:
    if not raw:
        return None
    out: dict[str, int] = {}
    for cid, grade in raw.items():
        if isinstance(grade, int):
            out[cid] = grade
        elif isinstance(grade, str):
            out[cid] = GRADE_GAIN.get(grade, 1)
    return out or None


def retrieval_metrics(
    relevant: set[str],
    retrieved_ids: list[str],
    q_type: str,
    *,
    relevance_grades: dict[str, str] | None = None,
) -> dict[str, Any]:
    """计算单条评测样本的检索指标。

    参数:
        relevant: 标注的相关 chunk ID 集合。
        retrieved_ids: 检索返回的 chunk ID 列表（有序）。
        q_type: 问题类型；negative 期望空检索。
        relevance_grades: v2 可选分级标注。

    返回:
        chunk 级 precision/recall、IR 指标及 negative_ok。
    """
    retrieved_set = set(retrieved_ids)
    if q_type == "negative":
        empty_retrieval = len(retrieved_set) == 0
        return {
            "context_recall": 1.0 if empty_retrieval else 0.0,
            "context_precision": 1.0 if empty_retrieval else 0.0,
            "context_precision_chunk": 1.0 if empty_retrieval else 0.0,
            "context_recall_chunk": 1.0 if empty_retrieval else 0.0,
            "retrieval_hit": empty_retrieval,
            "negative_ok": empty_retrieval,
            "mrr": None,
            "ndcg_at_5": None,
            "precision_at_1": None,
            "precision_at_3": None,
            "precision_at_5": None,
        }

    if not relevant:
        return {
            "context_recall": None,
            "context_precision": None,
            "context_precision_chunk": None,
            "context_recall_chunk": None,
            "retrieval_hit": False,
            "negative_ok": None,
            "mrr": None,
            "ndcg_at_5": None,
            "precision_at_1": None,
            "precision_at_3": None,
            "precision_at_5": None,
        }

    hit = bool(relevant & retrieved_set)
    recall = len(relevant & retrieved_set) / len(relevant)
    precision = len(relevant & retrieved_set) / len(retrieved_set) if retrieved_set else 0.0
    grade_map = _normalize_relevance_grades(relevance_grades)

    return {
        "context_recall": round(recall, 4),
        "context_precision": round(precision, 4),
        "context_precision_chunk": round(precision, 4),
        "context_recall_chunk": round(recall, 4),
        "retrieval_hit": hit,
        "negative_ok": None,
        "mrr": compute_mrr(retrieved_ids, relevant),
        "ndcg_at_5": compute_ndcg(retrieved_ids, relevant, relevance_grades=grade_map, k=5),
        "precision_at_1": compute_precision_at_k(retrieved_ids, relevant, 1),
        "precision_at_3": compute_precision_at_k(retrieved_ids, relevant, 3),
        "precision_at_5": compute_precision_at_k(retrieved_ids, relevant, 5),
    }
