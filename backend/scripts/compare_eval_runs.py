"""对比两次 RAG 评测报告的关键指标差异（Phase 1 P1）。

运行方式（在 backend 目录）:
  python scripts/compare_eval_runs.py \\
    --before ../data/eval_baseline_report_v1.json \\
    --after  ../data/eval_baseline_report.json

  python scripts/compare_eval_runs.py --before a.json --after b.json --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

# 对比指标（aggregate 与 near_domain 分项）
COMPARE_METRICS = (
    "context_precision_chunk",
    "context_recall_chunk",
    "context_precision_mean",
    "context_recall_mean",
    "mrr_mean",
    "ndcg_at_5_mean",
    "retrieval_hit_rate",
    "negative_reject_rate",
    "faithfulness_mean",
    "answer_relevancy_mean",
    "llm_judge_faithfulness_mean",
    "sample_count",
)


def _load_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"report not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _metric_delta(before: float | None, after: float | None) -> float | None:
    if before is None or after is None:
        return None
    return round(after - before, 4)


def compare_reports(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """对比两份报告的 aggregate 与 by_negative_subtype。"""
    b_agg = before.get("aggregate") or {}
    a_agg = after.get("aggregate") or {}

    metrics: dict[str, dict[str, Any]] = {}
    for key in COMPARE_METRICS:
        bv = b_agg.get(key)
        av = a_agg.get(key)
        if bv is None and av is None:
            continue
        metrics[key] = {
            "before": bv,
            "after": av,
            "delta": _metric_delta(
                float(bv) if bv is not None else None,
                float(av) if av is not None else None,
            ),
        }

    subtype_compare: dict[str, dict[str, Any]] = {}
    b_sub = before.get("by_negative_subtype") or {}
    a_sub = after.get("by_negative_subtype") or {}
    for subtype in sorted(set(b_sub) | set(a_sub)):
        bm = b_sub.get(subtype) or {}
        am = a_sub.get(subtype) or {}
        subtype_compare[subtype] = {
            "negative_reject_rate": {
                "before": bm.get("negative_reject_rate"),
                "after": am.get("negative_reject_rate"),
                "delta": _metric_delta(
                    bm.get("negative_reject_rate"),
                    am.get("negative_reject_rate"),
                ),
            },
            "sample_count": {
                "before": bm.get("sample_count"),
                "after": am.get("sample_count"),
            },
        }

    return {
        "before": {
            "path_meta": before.get("generated_at"),
            "dataset_version": before.get("dataset_version"),
        },
        "after": {
            "path_meta": after.get("generated_at"),
            "dataset_version": after.get("dataset_version"),
        },
        "metrics": metrics,
        "by_negative_subtype": subtype_compare,
    }


def format_comparison(comp: dict[str, Any]) -> str:
    """人类可读对比摘要。"""
    lines = [
        "Eval run comparison",
        f"  before: dataset={comp['before'].get('dataset_version')} "
        f"generated_at={comp['before'].get('path_meta')}",
        f"  after:  dataset={comp['after'].get('dataset_version')} "
        f"generated_at={comp['after'].get('path_meta')}",
        "",
        "Aggregate metrics (after - before):",
    ]
    for key, row in comp.get("metrics", {}).items():
        delta = row.get("delta")
        sign = ""
        if delta is not None:
            sign = " ↑" if delta > 0 else (" ↓" if delta < 0 else " =")
        lines.append(f"  {key}: {row.get('before')} -> {row.get('after')} (Δ {delta}){sign}")

    sub = comp.get("by_negative_subtype") or {}
    if sub:
        lines.append("")
        lines.append("Negative subtypes:")
        for subtype, row in sub.items():
            nrr = row.get("negative_reject_rate") or {}
            lines.append(
                f"  {subtype} NRR: {nrr.get('before')} -> {nrr.get('after')} (Δ {nrr.get('delta')})"
            )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two eval baseline reports")
    parser.add_argument("--before", required=True, help="Baseline report JSON path")
    parser.add_argument("--after", required=True, help="New report JSON path")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    args = parser.parse_args()

    before_path = Path(args.before)
    after_path = Path(args.after)
    if not before_path.is_absolute():
        before_path = (ROOT / before_path).resolve() if not before_path.exists() else before_path
    if not after_path.is_absolute():
        after_path = (ROOT / after_path).resolve() if not after_path.exists() else after_path

    try:
        before = _load_report(before_path)
        after = _load_report(after_path)
    except FileNotFoundError as exc:
        print(f"FAIL: {exc}")
        return 1

    comp = compare_reports(before, after)
    if args.json:
        print(json.dumps(comp, ensure_ascii=False, indent=2))
    else:
        print(format_comparison(comp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
