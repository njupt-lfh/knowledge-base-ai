"""Phase 3 出口 + 统一复验 — 多跳对比 + 全量检索基线

用法（backend 目录）:
  python scripts/run_phase3_exit.py                    # 全量（需 Embedding API）
  python scripts/run_phase3_exit.py --skip-backfill      # 跳过 backfill
  python scripts/run_phase3_exit.py --mock-backfill      # backfill 用规则抽取

输出: ../data/phase3_exit_report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

DATA_FILE = ROOT / "data" / "eval_qa_dataset.json"
PHASE0_FILE = ROOT / "data" / "eval_baseline_report_phase0.json"
REPORT_FILE = ROOT / "data" / "phase3_exit_report.json"


def _avg_recall(samples: list[dict]) -> float | None:
    vals = [s["context_recall"] for s in samples if s.get("context_recall") is not None]
    return round(mean(vals), 4) if vals else None


async def _eval_samples(
    samples: list[dict],
    *,
    mode: str,
    top_k: int,
) -> list[dict]:
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
                sources, route, paths = await agent.retrieve_for_eval(db, kb_id, question, top_k=top_k)
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


async def _run(args: argparse.Namespace) -> int:
    from app.core.config import settings

    if not DATA_FILE.exists():
        print(f"FAIL: missing {DATA_FILE}")
        return 1

    if settings.LLM_MOCK_MODE:
        print("WARN: LLM_MOCK_MODE=true — 向量检索将使用 mock embedding，仅适合冒烟")

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    all_samples = data["samples"]
    multi_hop = [s for s in all_samples if s.get("q_type") == "multi_hop"]

    if not args.skip_backfill:
        cmd = [sys.executable, str(BACKEND / "scripts" / "backfill_graph.py"), "--eval-kbs-only", "--skip-existing"]
        if args.mock_backfill:
            cmd.append("--mock")
        print("Running backfill:", " ".join(cmd))
        rc = subprocess.call(cmd, cwd=str(BACKEND))
        if rc != 0:
            print("FAIL: backfill_graph.py")
            return rc

    print(f"\n=== Multi-hop eval ({len(multi_hop)} samples) ===")
    vector_rows = await _eval_samples(multi_hop, mode="vector", top_k=args.top_k)
    agent_rows = await _eval_samples(multi_hop, mode="agent", top_k=args.top_k)

    vec_recall = _avg_recall(vector_rows)
    agent_recall = _avg_recall(agent_rows)
    rel_improve = None
    if vec_recall and vec_recall > 0 and agent_recall is not None:
        rel_improve = round((agent_recall - vec_recall) / vec_recall * 100, 2)

    multi_hop_pass = rel_improve is not None and rel_improve >= 20.0

    print(f"\n=== Multi-hop hybrid baseline ===")
    hybrid_rows = await _eval_samples(multi_hop, mode="hybrid", top_k=args.top_k)
    hybrid_recall = _avg_recall(hybrid_rows)
    hybrid_improve = None
    if hybrid_recall and hybrid_recall > 0 and agent_recall is not None:
        hybrid_improve = round((agent_recall - hybrid_recall) / hybrid_recall * 100, 2)

    print(f"\n=== Full retrieval eval ({len(all_samples)} samples, agent+abstention) ===")
    full_rows = await _eval_samples(all_samples, mode="agent", top_k=args.top_k)

    non_neg = [r for r in full_rows if r.get("q_type") != "negative"]
    neg = [r for r in full_rows if r.get("q_type") == "negative"]
    full_recall = _avg_recall(full_rows)
    pos_recall = _avg_recall(non_neg)
    neg_empty = round(mean(1.0 if r.get("context_recall") == 1.0 else 0.0 for r in neg), 4) if neg else None
    hit_rate = round(mean(1.0 if r.get("retrieval_hit") else 0.0 for r in non_neg), 4) if non_neg else None

    phase0_recall = None
    if PHASE0_FILE.exists():
        p0 = json.loads(PHASE0_FILE.read_text(encoding="utf-8"))
        phase0_recall = (p0.get("aggregate") or {}).get("context_recall_mean")

    rel_vs_p0 = None
    if phase0_recall and full_recall is not None and phase0_recall > 0:
        rel_vs_p0 = round((full_recall - phase0_recall) / phase0_recall * 100, 2)

    report = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "top_k": args.top_k,
            "mock_backfill": args.mock_backfill,
            "llm_mock_mode": settings.LLM_MOCK_MODE,
            "graph_enabled": settings.GRAPH_ENABLED,
            "abstain_enabled": settings.RETRIEVAL_ABSTAIN_ENABLED,
        },
        "multi_hop_eval": {
            "sample_count": len(multi_hop),
            "vector_recall_mean": vec_recall,
            "agent_recall_mean": agent_recall,
            "relative_improvement_pct": rel_improve,
            "target_improvement_pct": 20.0,
            "hybrid_recall_mean": hybrid_recall,
            "agent_vs_hybrid_improvement_pct": hybrid_improve,
            "pass": multi_hop_pass,
            "hybrid_samples": hybrid_rows,
            "agent_samples": agent_rows,
        },
        "unified_retrieval_eval": {
            "sample_count": len(full_rows),
            "context_recall_mean": full_recall,
            "positive_recall_mean": pos_recall,
            "negative_empty_rate": neg_empty,
            "retrieval_hit_rate": hit_rate,
            "phase0_recall_mean": phase0_recall,
            "relative_vs_phase0_pct": rel_vs_p0,
            "phase0_target_recall": round(phase0_recall * 1.15, 4) if phase0_recall else None,
            "pass_vs_phase0_15pct": bool(rel_vs_p0 is not None and rel_vs_p0 >= 15.0),
        },
        "exit_summary": {
            "multi_hop_graph_vs_vector": "PASS" if multi_hop_pass else "FAIL",
            "unified_recall_vs_phase0": "PASS" if rel_vs_p0 and rel_vs_p0 >= 15.0 else "PARTIAL/FAIL",
        },
    }

    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== Phase 3 Exit Summary ===")
    print(f"  Multi-hop: vector={vec_recall} hybrid={hybrid_recall} agent={agent_recall}")
    print(f"    vs vector Δ={rel_improve}% vs hybrid Δ={hybrid_improve}% -> {report['exit_summary']['multi_hop_graph_vs_vector']}")
    print(f"  Unified:   recall={full_recall} (P0={phase0_recall}, Δ={rel_vs_p0}%) neg_empty={neg_empty}")
    print(f"  Report -> {REPORT_FILE}")
    return 0 if multi_hop_pass else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3 exit + unified retrieval re-eval")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--skip-backfill", action="store_true")
    parser.add_argument("--mock-backfill", action="store_true", help="rule-based triple extraction")
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
