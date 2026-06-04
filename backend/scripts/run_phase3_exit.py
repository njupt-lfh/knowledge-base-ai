"""Phase 3 出口评测（v1.1 口径）

验证内容：
  - v2 multi_hop context_recall ≥ 0.82（≥50 条）
  - v1 回归：CR≥0.85、NRR=1.0（读取 eval_baseline_report_v1.json）

运行方式（在 backend 目录）:
  python scripts/run_phase3_exit.py --report-only
  python scripts/run_phase3_exit.py --mock-backfill

预期结果：打印 PASS 并退出码 0；未达标时退出码 1。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

DATA_FILE_V1 = ROOT / "data" / "eval_qa_dataset.json"
DATA_FILE_V2 = ROOT / "data" / "eval_qa_dataset_v2.json"
REPORT_V1 = ROOT / "data" / "eval_baseline_report_v1.json"
REPORT_V2 = ROOT / "data" / "eval_baseline_report_v2.json"
REPORT_FILE = ROOT / "data" / "phase3_exit_report.json"

V2_MULTI_HOP_CR_TARGET = 0.82
V2_MULTI_HOP_MIN_SAMPLES = 50
V1_CR_TARGET = 0.85
V1_NRR_TARGET = 1.0


def _recall_mean(rows: list[dict]) -> float | None:
    """计算 context_recall 均值。"""
    vals = [r["context_recall"] for r in rows if r.get("context_recall") is not None]
    return round(mean(vals), 4) if vals else None


def _metric_from_block(block: dict | None, key: str) -> float | None:
    """从 aggregate / by_question_type 块读取指标，兼容 chunk 别名。"""
    if not block:
        return None
    val = block.get(key)
    if val is None and key == "context_recall_mean":
        val = block.get("context_recall_chunk")
    if val is None and key == "context_precision_mean":
        val = block.get("context_precision_chunk")
    return float(val) if val is not None else None


def _check_v1_regression(v1_report: dict | None) -> dict[str, object]:
    """v1 回归门禁（读取已有报告）。"""
    if not v1_report:
        return {
            "available": False,
            "context_recall_mean": None,
            "negative_reject_rate": None,
            "multi_hop_recall_mean": None,
            "pass": False,
            "reason": f"missing report: {REPORT_V1}",
        }

    agg = v1_report.get("aggregate") or {}
    mh = (v1_report.get("by_question_type") or {}).get("multi_hop") or {}
    cr = _metric_from_block(agg, "context_recall_mean")
    nrr = _metric_from_block(agg, "negative_reject_rate")
    mh_cr = _metric_from_block(mh, "context_recall_mean")

    ok = cr is not None and cr >= V1_CR_TARGET and nrr is not None and nrr >= V1_NRR_TARGET
    return {
        "available": True,
        "context_recall_mean": cr,
        "negative_reject_rate": nrr,
        "multi_hop_recall_mean": mh_cr,
        "target_cr": V1_CR_TARGET,
        "target_nrr": V1_NRR_TARGET,
        "pass": ok,
        "reason": None if ok else "v1 CR/NRR below target",
    }


def _check_v2_multi_hop(v2_report: dict | None, *, min_samples: int) -> dict[str, object]:
    """v2 multi_hop 专项门禁。"""
    if not v2_report:
        return {
            "available": False,
            "context_recall_mean": None,
            "sample_count": 0,
            "target_cr": V2_MULTI_HOP_CR_TARGET,
            "min_samples": min_samples,
            "pass": False,
            "reason": f"missing report: {REPORT_V2}",
        }

    mh = (v2_report.get("by_question_type") or {}).get("multi_hop") or {}
    cr = _metric_from_block(mh, "context_recall_mean")
    count = int(mh.get("sample_count") or 0)

    reasons: list[str] = []
    if count < min_samples:
        reasons.append(f"sample_count {count} < {min_samples}")
    if cr is None:
        reasons.append("context_recall_mean missing")
    elif cr < V2_MULTI_HOP_CR_TARGET:
        reasons.append(f"context_recall_mean {cr} < {V2_MULTI_HOP_CR_TARGET}")

    return {
        "available": True,
        "context_recall_mean": cr,
        "sample_count": count,
        "target_cr": V2_MULTI_HOP_CR_TARGET,
        "min_samples": min_samples,
        "pass": not reasons,
        "reason": "; ".join(reasons) if reasons else None,
    }


async def _eval_samples(
    samples: list[dict],
    *,
    mode: str,
    top_k: int,
) -> list[dict]:
    """对样本列表按指定检索模式评测。"""
    from app.core.database import async_session
    from app.eval.retrieval_metrics import retrieval_metrics
    from app.services.agent_orchestrator import AgentOrchestrator
    from app.services.hybrid_retriever import HybridRetriever

    agent = AgentOrchestrator()
    hybrid = HybridRetriever()
    rows: list[dict] = []

    async with async_session() as db:
        for s in samples:
            kb_id = s["kb_id"]
            question = s["question"]
            relevant = {x for x in (s.get("relevant_chunk_ids") or []) if x}

            t0 = time.perf_counter()
            if mode == "vector":
                sources = await hybrid.vector_only_search(db, kb_id, question, top_k=top_k)
            elif mode == "hybrid":
                sources = await hybrid.search(db, kb_id, question, top_k=top_k)
            else:
                sources, _route, _paths = await agent.retrieve_for_eval(
                    db, kb_id, question, top_k=top_k
                )
            ms = round((time.perf_counter() - t0) * 1000, 1)

            retrieved_ids = [x["chunk_id"] for x in sources]
            metrics = retrieval_metrics(relevant, retrieved_ids, s["q_type"])
            rows.append(
                {
                    "id": s["id"],
                    "q_type": s["q_type"],
                    "mode": mode,
                    "retrieve_ms": ms,
                    **metrics,
                }
            )
            print(f"  [{mode}] {s['id']} recall={metrics.get('context_recall')}")

    return rows


def _live_v2_report_from_rows(rows: list[dict]) -> dict[str, object]:
    """由 live multi_hop 样本构造 v2 门禁检查用报告片段。"""
    return {
        "by_question_type": {
            "multi_hop": {
                "sample_count": len(rows),
                "context_recall_mean": _recall_mean(rows),
            }
        }
    }


async def _run(args: argparse.Namespace) -> int:
    """执行主逻辑并返回进程退出码。"""
    from app.core.config import settings

    min_samples = args.min_multi_hop_samples
    v1_report = json.loads(REPORT_V1.read_text(encoding="utf-8")) if REPORT_V1.exists() else None
    v2_report = json.loads(REPORT_V2.read_text(encoding="utf-8")) if REPORT_V2.exists() else None

    live_rows: list[dict] | None = None
    multi_hop_samples: list[dict] | None = None

    if not args.report_only:
        if not DATA_FILE_V2.exists():
            print(f"FAIL: missing {DATA_FILE_V2}")
            return 1

        if settings.LLM_MOCK_MODE:
            print("WARN: LLM_MOCK_MODE=true — 向量检索将使用 mock embedding，仅适合冒烟")

        if not args.skip_backfill:
            cmd = [
                sys.executable,
                str(BACKEND / "scripts" / "backfill_graph.py"),
                "--eval-kbs-only",
                "--skip-existing",
            ]
            if args.mock_backfill:
                cmd.append("--mock")
            print("Running backfill:", " ".join(cmd))
            rc = subprocess.call(cmd, cwd=str(BACKEND))
            if rc != 0:
                print("FAIL: backfill_graph.py")
                return rc

        data = json.loads(DATA_FILE_V2.read_text(encoding="utf-8"))
        multi_hop_samples = [s for s in data["samples"] if s.get("q_type") == "multi_hop"]
        if len(multi_hop_samples) < min_samples:
            print(f"FAIL: v2 dataset multi_hop={len(multi_hop_samples)} < {min_samples}")
            return 1

        print(f"\n=== v2 Multi-hop live eval ({len(multi_hop_samples)} samples, agent) ===")
        live_rows = await _eval_samples(multi_hop_samples, mode="agent", top_k=args.top_k)
        v2_report = _live_v2_report_from_rows(live_rows)

    v2_check = _check_v2_multi_hop(v2_report, min_samples=min_samples)
    v1_check = _check_v1_regression(v1_report)

    # 参考指标：multi_hop agent vs vector（非门禁）
    reference: dict[str, object] = {}
    if live_rows and multi_hop_samples and not args.report_only:
        vec_rows = await _eval_samples(multi_hop_samples, mode="vector", top_k=args.top_k)
        vec_recall = _recall_mean(vec_rows)
        agent_recall = _recall_mean(live_rows)
        rel_improve = None
        if vec_recall and vec_recall > 0 and agent_recall is not None:
            rel_improve = round((agent_recall - vec_recall) / vec_recall * 100, 2)
        reference = {
            "vector_recall_mean": vec_recall,
            "agent_recall_mean": agent_recall,
            "relative_improvement_pct": rel_improve,
            "legacy_target_improvement_pct": 20.0,
        }

    all_pass = bool(v2_check["pass"] and v1_check["pass"])

    report = {
        "version": "2.0",
        "criteria": "v1.1 Phase 3.4",
        "generated_at": datetime.now(UTC).isoformat(),
        "config": {
            "top_k": args.top_k,
            "report_only": args.report_only,
            "mock_backfill": args.mock_backfill,
            "min_multi_hop_samples": min_samples,
            "llm_mock_mode": settings.LLM_MOCK_MODE,
            "graph_enabled": settings.GRAPH_ENABLED,
            "abstain_enabled": settings.RETRIEVAL_ABSTAIN_ENABLED,
        },
        "v2_multi_hop_gate": v2_check,
        "v1_regression_gate": v1_check,
        "reference_multi_hop_vs_vector": reference,
        "live_samples": live_rows,
        "exit_summary": {
            "v2_multi_hop_cr": "PASS" if v2_check["pass"] else "FAIL",
            "v1_regression": "PASS" if v1_check["pass"] else "FAIL",
            "overall": "PASS" if all_pass else "FAIL",
        },
    }

    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== Phase 3 Exit Summary (v1.1) ===")
    print(
        f"  v2 multi_hop: CR={v2_check.get('context_recall_mean')} "
        f"n={v2_check.get('sample_count')} target>={V2_MULTI_HOP_CR_TARGET} "
        f"-> {report['exit_summary']['v2_multi_hop_cr']}"
    )
    if v2_check.get("reason"):
        print(f"    reason: {v2_check['reason']}")
    print(
        f"  v1 regression: CR={v1_check.get('context_recall_mean')} "
        f"NRR={v1_check.get('negative_reject_rate')} "
        f"-> {report['exit_summary']['v1_regression']}"
    )
    if v1_check.get("reason"):
        print(f"    reason: {v1_check['reason']}")
    if reference:
        print(
            f"  (reference) agent vs vector Δ={reference.get('relative_improvement_pct')}% "
            f"(legacy +20% gate, informational only)"
        )
    print(f"  Report -> {REPORT_FILE}")
    return 0 if all_pass else 1


def main() -> int:
    """脚本 CLI 入口。"""
    parser = argparse.ArgumentParser(description="Phase 3 exit eval (v1.1: v2 multi_hop CR≥0.82)")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--skip-backfill", action="store_true")
    parser.add_argument("--mock-backfill", action="store_true", help="rule-based triple extraction")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="仅校验 eval_baseline_report_v1/v2.json，不跑 live eval",
    )
    parser.add_argument(
        "--min-multi-hop-samples",
        type=int,
        default=V2_MULTI_HOP_MIN_SAMPLES,
        help="v2 multi_hop 最少样本数（默认 50）",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
