"""CI 评测门禁阈值与检查逻辑。"""

from __future__ import annotations

from typing import Any

CI_GATES: dict[str, dict[str, float]] = {
    "v1_baseline": {
        "context_recall_mean": 0.80,
        "retrieval_hit_rate": 0.88,
    },
    "week0": {
        "negative_reject_rate": 0.78,
        "context_recall_mean": 0.85,
        "retrieval_hit_rate": 0.88,
    },
    "week2": {
        "context_precision_mean": 0.35,
        "context_precision_chunk": 0.35,
        "negative_reject_rate": 0.78,
        "context_recall_mean": 0.85,
    },
    "week2_v2": {
        "context_precision_mean": 0.30,
        "context_precision_chunk": 0.30,
        "negative_reject_rate": 0.70,
        "context_recall_mean": 0.80,
    },
    "week4": {
        "faithfulness_mean": 0.75,
        "answer_relevancy_mean": 0.48,
        "context_precision_mean": 0.42,
        "context_precision_chunk": 0.42,
        "negative_reject_rate": 0.82,
    },
    "week4_quality": {
        "context_precision_chunk": 0.50,
        "negative_reject_rate": 0.95,
        "context_recall_mean": 0.85,
        "context_recall_chunk": 0.85,
    },
}


def _get_metric(agg: dict[str, Any], key: str) -> float | None:
    v = agg.get(key)
    if v is None and key == "context_precision_chunk":
        v = agg.get("context_precision_mean")
    if v is None and key == "context_recall_mean":
        v = agg.get("context_recall_chunk")
    return float(v) if v is not None else None


def check_gates(report: dict[str, Any], phase: str) -> tuple[bool, list[str]]:
    """检查报告 aggregate 是否满足指定阶段门禁。"""
    gates = CI_GATES.get(phase)
    if not gates:
        return False, [f"unknown phase: {phase}"]

    agg = report.get("aggregate") or {}
    failures: list[str] = []
    for key, minimum in gates.items():
        val = _get_metric(agg, key)
        if val is None:
            failures.append(f"{key}: missing (required >= {minimum})")
        elif val < minimum:
            failures.append(f"{key}: {val} < {minimum}")

    return len(failures) == 0, failures
