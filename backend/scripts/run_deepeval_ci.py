"""Phase 2.4 CI 评测：DeepEval 门禁 + Knowledge Retention 回归

用法（在 backend 目录）:
  python scripts/run_deepeval_ci.py              # 默认 offline 门禁（无需 API）
  python scripts/run_deepeval_ci.py --live       # 真实 DeepEval + Volcengine Judge
  python scripts/run_deepeval_ci.py --retrieval  # 若有 eval 数据集，跑检索子集回归

输出: ../data/eval_deepeval_ci_report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

SMOKE_FIXTURE = BACKEND / "tests" / "fixtures" / "eval_smoke_samples.json"
DATA_FILE = ROOT / "data" / "eval_qa_dataset.json"
BASELINE_FILE = ROOT / "data" / "eval_baseline_report.json"
REPORT_FILE = ROOT / "data" / "eval_deepeval_ci_report.json"

from app.eval.deepeval_runner import (  # noqa: E402
    check_deepeval_gates,
    check_knowledge_retention,
    run_deepeval,
)
from app.eval.retrieval_metrics import retrieval_metrics  # noqa: E402


async def _retrieval_smoke(limit: int = 8) -> dict[str, Any]:
    from app.core.database import async_session
    from app.services.rag_service import RAGService

    if not DATA_FILE.exists():
        return {"skipped": True, "reason": "eval_qa_dataset.json missing"}

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    samples = data.get("samples", [])[:limit]
    rag = RAGService()
    recalls: list[float] = []

    async with async_session() as db:
        for s in samples:
            if s.get("q_type") == "negative":
                continue
            sources = await rag.retrieve(s["kb_id"], s["question"], top_k=5, db=db)
            relevant = {x for x in (s.get("relevant_chunk_ids") or []) if x}
            retrieved = [x["chunk_id"] for x in sources]
            m = retrieval_metrics(relevant, retrieved, s["q_type"])
            if m.get("context_recall") is not None:
                recalls.append(float(m["context_recall"]))

    if not recalls:
        return {"skipped": True, "reason": "no recall samples"}

    return {
        "skipped": False,
        "sample_count": len(recalls),
        "context_recall_mean": round(mean(recalls), 4),
        "context_precision_mean": None,
    }


async def _run(args: argparse.Namespace) -> int:
    smoke = json.loads(SMOKE_FIXTURE.read_text(encoding="utf-8"))
    deepeval_scores = run_deepeval(smoke, prefer_live=args.live)
    deepeval_gates = check_deepeval_gates(deepeval_scores)

    retention: dict[str, Any] = {"skipped": True, "reason": "no baseline report"}
    retrieval_agg: dict[str, Any] = {"skipped": True}

    if args.retrieval and DATA_FILE.exists():
        retrieval_agg = await _retrieval_smoke(args.limit)
        if not retrieval_agg.get("skipped") and BASELINE_FILE.exists():
            baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
            retention = check_knowledge_retention(
                baseline.get("aggregate") or {},
                retrieval_agg,
                min_recall_ratio=args.min_recall_ratio,
            )
            retention["skipped"] = False

    all_passed = deepeval_gates["passed"] and (
        retention.get("skipped") or retention.get("passed", False)
    )

    report = {
        "version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "phase": "2.4",
        "config": {
            "live": args.live,
            "retrieval": args.retrieval,
            "min_recall_ratio": args.min_recall_ratio,
        },
        "deepeval": deepeval_scores,
        "deepeval_gates": deepeval_gates,
        "retrieval_smoke": retrieval_agg,
        "knowledge_retention": retention,
        "passed": all_passed,
    }

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  deepeval mode={deepeval_scores.get('mode')}")
    print(f"  hallucination_mean={deepeval_scores.get('hallucination_mean')}")
    print(f"  contextual_relevancy_mean={deepeval_scores.get('contextual_relevancy_mean')}")
    print(f"  deepeval_gates={'PASS' if deepeval_gates['passed'] else 'FAIL'}")
    if not retention.get("skipped"):
        print(f"  knowledge_retention={'PASS' if retention.get('passed') else 'FAIL'}")

    if all_passed:
        print(f"PASS: report -> {REPORT_FILE}")
        return 0

    print(f"FAIL: CI gates not met -> {REPORT_FILE}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="DeepEval CI gates (Phase 2.4)")
    parser.add_argument("--live", action="store_true", help="使用真实 DeepEval + Volcengine")
    parser.add_argument("--retrieval", action="store_true", help="跑检索冒烟 + 基线 retention")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--min-recall-ratio", type=float, default=0.85)
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
