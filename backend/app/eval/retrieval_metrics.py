"""Chunk 级检索评测指标（与 RAGAS context_recall / context_precision 对齐）"""

from __future__ import annotations

from typing import Any


def retrieval_metrics(
    relevant: set[str],
    retrieved_ids: list[str],
    q_type: str,
) -> dict[str, Any]:
    retrieved_set = set(retrieved_ids)
    if q_type == "negative":
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
