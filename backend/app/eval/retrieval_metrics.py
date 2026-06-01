"""Chunk 级检索评测指标（与 RAGAS context_recall / context_precision 对齐）。

提供 `retrieval_metrics` 函数，基于相关 chunk ID 集合与召回列表
计算命中率、召回率与精确率，支持负样本（期望空检索）场景。
"""

from __future__ import annotations

from typing import Any


def retrieval_metrics(
    relevant: set[str],
    retrieved_ids: list[str],
    q_type: str,
) -> dict[str, Any]:
    """计算单条评测样本的检索指标。

    参数:
        relevant: 标注的相关 chunk ID 集合。
        retrieved_ids: 检索返回的 chunk ID 列表（有序）。
        q_type: 问题类型；`negative` 表示负样本，期望不召回任何 chunk。

    返回:
        含 context_recall、context_precision、retrieval_hit、negative_ok 的字典。
    """
    retrieved_set = set(retrieved_ids)
    if q_type == "negative":
        # 负样本：空检索视为完全正确
        empty_retrieval = len(retrieved_set) == 0
        return {
            "context_recall": 1.0 if empty_retrieval else 0.0,
            "context_precision": 1.0 if empty_retrieval else 0.0,
            "retrieval_hit": empty_retrieval,
            "negative_ok": empty_retrieval,
        }
    if not relevant:
        return {
            "context_recall": None,
            "context_precision": None,
            "retrieval_hit": False,
            "negative_ok": None,
        }
    hit = bool(relevant & retrieved_set)
    recall = len(relevant & retrieved_set) / len(relevant)
    precision = len(relevant & retrieved_set) / len(retrieved_set) if retrieved_set else 0.0
    return {
        "context_recall": round(recall, 4),
        "context_precision": round(precision, 4),
        "retrieval_hit": hit,
        "negative_ok": None,
    }
