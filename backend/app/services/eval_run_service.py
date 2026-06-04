"""评测运行持久化与趋势查询（Week 3）。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.eval_run import EvalRun, EvalSampleResult


def _utc_iso(dt) -> str | None:
    """eval_runs.created_at 存 UTC naive，API 统一带 Z 便于前端按 UTC 展示。"""
    if dt is None:
        return None
    return dt.isoformat() + "Z"


TREND_METRICS = (
    "context_precision_chunk",
    "context_recall_mean",
    "context_recall_chunk",
    "mrr_mean",
    "ndcg_at_5_mean",
    "negative_reject_rate",
    "faithfulness_mean",
    "answer_relevancy_mean",
)


def _metric_from_aggregate(agg: dict[str, Any], metric: str) -> float | None:
    v = agg.get(metric)
    if v is None and metric == "context_precision_chunk":
        v = agg.get("context_precision_mean")
    if v is None and metric == "context_recall_mean":
        v = agg.get("context_recall_chunk")
    return float(v) if v is not None else None


async def persist_eval_report(
    db: AsyncSession,
    report: dict[str, Any],
    *,
    ci_phase: str | None = None,
) -> str:
    """将评测报告写入 eval_runs / eval_sample_results。"""
    agg = report.get("aggregate") or {}
    config = report.get("config") or {}
    run = EvalRun(
        dataset_version=str(report.get("dataset_version") or config.get("dataset") or "v1"),
        eval_mode=str(config.get("eval_mode") or "retrieval_only"),
        ci_phase=ci_phase,
        sample_count=int(agg.get("sample_count") or config.get("sample_count") or 0),
        report_json=json.dumps(report, ensure_ascii=False),
        aggregate_json=json.dumps(agg, ensure_ascii=False),
    )
    db.add(run)
    await db.flush()

    for row in report.get("samples") or []:
        metrics = {
            k: row.get(k)
            for k in (
                "context_recall",
                "context_precision_chunk",
                "context_precision",
                "retrieval_hit",
                "mrr",
                "ndcg_at_5",
                "negative_ok",
                "faithfulness",
                "answer_relevancy",
            )
            if row.get(k) is not None
        }
        db.add(
            EvalSampleResult(
                run_id=run.id,
                sample_id=str(row.get("id") or ""),
                kb_id=str(row.get("kb_id") or ""),
                q_type=str(row.get("q_type") or "unknown"),
                metrics_json=json.dumps(metrics, ensure_ascii=False),
            )
        )

    await db.commit()
    return run.id


async def list_eval_runs(db: AsyncSession, *, limit: int = 20) -> list[dict[str, Any]]:
    """最近评测运行列表（不含全量 samples）。"""
    rows = (
        await db.execute(select(EvalRun).order_by(desc(EvalRun.created_at)).limit(limit))
    ).scalars().all()
    out: list[dict[str, Any]] = []
    for r in rows:
        agg = json.loads(r.aggregate_json)
        out.append(
            {
                "id": r.id,
                "created_at": _utc_iso(r.created_at),
                "dataset_version": r.dataset_version,
                "eval_mode": r.eval_mode,
                "ci_phase": r.ci_phase,
                "sample_count": r.sample_count,
                "aggregate": agg,
            }
        )
    return out


async def get_eval_run(db: AsyncSession, run_id: str) -> dict[str, Any] | None:
    """获取单次运行完整报告。"""
    run = await db.get(EvalRun, run_id)
    if not run:
        return None
    return json.loads(run.report_json)


async def metric_trend(
    db: AsyncSession,
    metric: str,
    *,
    limit: int = 20,
    dataset_version: str | None = None,
) -> list[dict[str, Any]]:
    """指标历史趋势（按 created_at 升序）。"""
    if metric not in TREND_METRICS:
        metric = "context_precision_chunk"

    q = select(EvalRun)
    if dataset_version:
        q = q.where(EvalRun.dataset_version == dataset_version)
    q = q.order_by(desc(EvalRun.created_at)).limit(limit)
    rows = list((await db.execute(q)).scalars().all())
    rows.reverse()

    points: list[dict[str, Any]] = []
    for r in rows:
        agg = json.loads(r.aggregate_json)
        val = _metric_from_aggregate(agg, metric)
        points.append(
            {
                "run_id": r.id,
                "created_at": _utc_iso(r.created_at),
                "dataset_version": r.dataset_version,
                "eval_mode": r.eval_mode,
                "value": val,
            }
        )
    return points
