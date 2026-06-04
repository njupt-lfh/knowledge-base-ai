"""评测结果聚合（按全体 / 题型 / 知识库）。

供 run_rag_eval.py 与 CI 门禁复用。
"""

from __future__ import annotations

from statistics import mean
from typing import Any, Callable


def _avg(samples: list[dict], key: str) -> float | None:
    vals = [s[key] for s in samples if s.get(key) is not None]
    return round(mean(vals), 4) if vals else None


def aggregate_sample_metrics(samples: list[dict]) -> dict[str, Any]:
    """对样本列表计算均值类聚合指标（含 chunk 级 IR 指标）。"""
    non_neg = [s for s in samples if s.get("q_type") != "negative"]
    neg = [s for s in samples if s.get("q_type") == "negative"]

    ragas_f = _avg(samples, "faithfulness")
    ragas_ar = _avg(samples, "answer_relevancy")

    cp_chunk = _avg(non_neg, "context_precision")
    cr_chunk = _avg(non_neg, "context_recall")

    return {
        "sample_count": len(samples),
        # chunk 级（明确别名，兼容旧字段）
        "context_precision_chunk": cp_chunk,
        "context_recall_chunk": cr_chunk,
        "context_precision_mean": cp_chunk,
        "context_recall_mean": cr_chunk,
        "mrr_mean": _avg(non_neg, "mrr"),
        "ndcg_at_5_mean": _avg(non_neg, "ndcg_at_5"),
        "precision_at_1_mean": _avg(non_neg, "precision_at_1"),
        "precision_at_3_mean": _avg(non_neg, "precision_at_3"),
        "precision_at_5_mean": _avg(non_neg, "precision_at_5"),
        "retrieval_hit_rate": round(
            mean(1.0 if s.get("retrieval_hit") else 0.0 for s in non_neg), 4
        )
        if non_neg
        else None,
        "negative_reject_rate": round(mean(1.0 if s.get("negative_ok") else 0.0 for s in neg), 4)
        if neg
        else None,
        "faithfulness_mean": ragas_f,
        "answer_relevancy_mean": ragas_ar,
        "llm_judge_faithfulness_mean": _avg(samples, "llm_judge_faithfulness"),
        "avg_retrieve_ms": _avg(samples, "retrieve_ms"),
        "avg_generate_ms": _avg(samples, "generate_ms"),
    }


def aggregate_by_key(
    samples: list[dict],
    key_fn: Callable[[dict], str],
) -> dict[str, dict[str, Any]]:
    """按任意键分组聚合。"""
    groups: dict[str, list[dict]] = {}
    for s in samples:
        k = key_fn(s) or "unknown"
        groups.setdefault(k, []).append(s)
    return {k: aggregate_sample_metrics(v) for k, v in sorted(groups.items())}


def aggregate_by_negative_subtype(samples: list[dict]) -> dict[str, dict[str, Any]]:
    """v2 负例子类型（near_domain / unrelated）分项聚合。"""
    neg = [s for s in samples if s.get("q_type") == "negative"]
    if not neg:
        return {}
    return aggregate_by_key(neg, lambda r: r.get("negative_subtype") or "unknown")


def merge_ragas_into_aggregate(agg: dict[str, Any], ragas_scores: dict[str, Any]) -> None:
    """将 RAGAS 分写入 aggregate（含 CP-ragas 别名）。"""
    if not ragas_scores:
        return
    agg["ragas"] = ragas_scores
    agg["context_precision_ragas"] = ragas_scores.get("context_precision")
    agg["context_recall_ragas"] = ragas_scores.get("context_recall")
    if ragas_scores.get("faithfulness") is not None:
        agg["faithfulness_mean"] = ragas_scores["faithfulness"]
    if ragas_scores.get("answer_relevancy") is not None:
        agg["answer_relevancy_mean"] = ragas_scores["answer_relevancy"]
