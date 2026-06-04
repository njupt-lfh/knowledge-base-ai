"""GRAPH_MODE A/B 评测（Phase 3b 最小脚本）。

对比 lite / linear / legacy 在 v2 multi_hop 上的 context_recall。

运行方式（在 backend 目录）:
  python scripts/run_graph_mode_ab.py --limit 10
  python scripts/run_graph_mode_ab.py --limit 0

输出: ../data/graph_mode_ab_report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

DATA_FILE_V2 = ROOT / "data" / "eval_qa_dataset_v2.json"
REPORT_FILE = ROOT / "data" / "graph_mode_ab_report.json"

MODES = ("lite", "linear", "legacy")
MULTI_HOP_CR_TARGET = 0.82


def _recall_mean(rows: list[dict]) -> float | None:
    vals = [r["context_recall"] for r in rows if r.get("context_recall") is not None]
    return round(mean(vals), 4) if vals else None


async def _eval_mode(
    samples: list[dict],
    mode: str,
    *,
    top_k: int,
) -> dict:
    """单模式评测 multi_hop 样本。"""
    from app.core.database import async_session
    from app.eval.retrieval_metrics import retrieval_metrics
    from app.services.agent_orchestrator import AgentOrchestrator

    agent = AgentOrchestrator()
    rows: list[dict] = []

    async with async_session() as db:
        for s in samples:
            question = s["question"]
            kb_id = s["kb_id"]
            relevant = {x for x in (s.get("relevant_chunk_ids") or []) if x}

            t0 = time.perf_counter()
            sources, _route, _paths = await agent.retrieve_for_eval(
                db,
                kb_id,
                question,
                top_k=top_k,
                graph_mode=mode,
            )
            ms = round((time.perf_counter() - t0) * 1000, 1)

            retrieved_ids = [x["chunk_id"] for x in sources]
            metrics = retrieval_metrics(relevant, retrieved_ids, s["q_type"])
            rows.append(
                {
                    "id": s["id"],
                    "mode": mode,
                    "retrieve_ms": ms,
                    "source_tags": sorted({x.get("source") for x in sources}),
                    **metrics,
                }
            )
            print(
                f"  [{mode}] {s['id']} recall={metrics.get('context_recall')} "
                f"ms={ms}"
            )

    cr = _recall_mean(rows)
    return {
        "graph_mode": mode,
        "sample_count": len(rows),
        "context_recall_mean": cr,
        "pass_cr_082": bool(cr is not None and cr >= MULTI_HOP_CR_TARGET),
        "samples": rows,
    }


async def _run(args: argparse.Namespace) -> int:
    from app.core.config import settings

    if not DATA_FILE_V2.exists():
        print(f"FAIL: missing {DATA_FILE_V2}")
        return 1

    data = json.loads(DATA_FILE_V2.read_text(encoding="utf-8"))
    samples = [s for s in data["samples"] if s.get("q_type") == "multi_hop"]
    if args.limit > 0:
        samples = samples[: args.limit]

    if not samples:
        print("FAIL: no multi_hop samples")
        return 1

    print(f"=== GRAPH_MODE A/B ({len(samples)} multi_hop samples) ===")
    print(f"  GRAPH_ENABLED={settings.GRAPH_ENABLED} default_MODE={settings.GRAPH_MODE}")

    results: list[dict] = []
    for mode in MODES:
        print(f"\n--- mode={mode} ---")
        results.append(await _eval_mode(samples, mode, top_k=args.top_k))

    baseline_cr = results[0]["context_recall_mean"]
    comparison: list[dict] = []
    for r in results[1:]:
        cr = r["context_recall_mean"]
        delta = None
        if baseline_cr is not None and cr is not None:
            delta = round(cr - baseline_cr, 4)
        comparison.append(
            {
                "mode": r["graph_mode"],
                "context_recall_mean": cr,
                "delta_vs_lite": delta,
            }
        )

    report = {
        "version": "1.0",
        "criteria": "Phase 3b GRAPH_MODE A/B",
        "generated_at": datetime.now(UTC).isoformat(),
        "config": {
            "dataset": "v2",
            "q_type": "multi_hop",
            "sample_count": len(samples),
            "top_k": args.top_k,
            "target_cr": MULTI_HOP_CR_TARGET,
            "modes": list(MODES),
        },
        "results": results,
        "comparison_vs_lite": comparison,
        "best_mode": max(
            results,
            key=lambda x: (x["context_recall_mean"] is not None, x["context_recall_mean"] or -1),
        )["graph_mode"],
    }

    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== GRAPH_MODE A/B Summary ===")
    for r in results:
        flag = "PASS" if r["pass_cr_082"] else "FAIL"
        print(f"  {r['graph_mode']:8s} CR={r['context_recall_mean']} -> {flag}")
    print(f"  best_mode={report['best_mode']}")
    print(f"  Report -> {REPORT_FILE}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="GRAPH_MODE lite/linear/legacy A/B on v2 multi_hop")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="multi_hop 样本上限，0=全部（默认 10 便于冒烟）",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
