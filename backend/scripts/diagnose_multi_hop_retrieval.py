"""multi_hop 检索诊断：seeds / 命中 0·1·2 / 来源标签。

运行方式（在 backend 目录）:
  python scripts/diagnose_multi_hop_retrieval.py --limit 10
  python scripts/diagnose_multi_hop_retrieval.py --limit 0

输出: ../data/multi_hop_retrieval_diagnosis.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

DATA_FILE_V2 = ROOT / "data" / "eval_qa_dataset_v2.json"
REPORT_FILE = ROOT / "data" / "multi_hop_retrieval_diagnosis.json"


async def _run(args: argparse.Namespace) -> int:
    from app.core.database import async_session
    from app.eval.retrieval_metrics import retrieval_metrics
    from app.services.agent_orchestrator import AgentOrchestrator
    from app.services.multi_hop_retrieval_service import (
        diagnose_retrieval_hits,
        extract_quote_anchors,
        get_multi_hop_anchors,
        should_use_multi_hop_split,
    )
    from app.services.query_router import route_query

    if not DATA_FILE_V2.exists():
        print(f"FAIL: missing {DATA_FILE_V2}")
        return 1

    data = json.loads(DATA_FILE_V2.read_text(encoding="utf-8"))
    samples = [s for s in data["samples"] if s.get("q_type") == "multi_hop"]
    if args.limit > 0:
        samples = samples[: args.limit]

    agent = AgentOrchestrator()
    rows: list[dict] = []
    bucket_counter: Counter[str] = Counter()

    async with async_session() as db:
        for s in samples:
            kb_id = s["kb_id"]
            question = s["question"]
            relevant = {x for x in (s.get("relevant_chunk_ids") or []) if x}
            route = route_query(question)
            anchors = get_multi_hop_anchors(question)
            quotes = extract_quote_anchors(question)

            sources, _route, _paths = await agent.retrieve_for_eval(
                db, kb_id, question, top_k=args.top_k,
            )
            retrieved = [x["chunk_id"] for x in sources]
            metrics = retrieval_metrics(relevant, retrieved, "multi_hop")
            diag = diagnose_retrieval_hits(relevant, retrieved)
            bucket_counter[diag["bucket"]] += 1

            tags = sorted({x.get("source", "?") for x in sources})
            rows.append(
                {
                    "id": s["id"],
                    "kb_id": kb_id,
                    "question": question[:120],
                    "route": route,
                    "anchors": anchors,
                    "quote_spans": quotes,
                    "split_enabled": should_use_multi_hop_split(route, question),
                    "retrieved_ids": retrieved,
                    "relevant_ids": sorted(relevant),
                    "hit": diag,
                    "source_tags": tags,
                    **metrics,
                }
            )
            print(
                f"  {s['id']} bucket={diag['bucket']} recall={metrics.get('context_recall')} "
                f"anchors={len(anchors)} tags={tags}"
            )

    recalls = [r["context_recall"] for r in rows if r.get("context_recall") is not None]
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "sample_count": len(rows),
        "context_recall_mean": round(mean(recalls), 4) if recalls else None,
        "hit_buckets": dict(bucket_counter),
        "samples": rows,
    }
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== multi_hop diagnosis ===")
    print(f"  CR mean = {report['context_recall_mean']}")
    print(f"  buckets = {report['hit_buckets']}")
    print(f"  -> {REPORT_FILE}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose multi_hop retrieval hits")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--limit", type=int, default=10, help="0 = all multi_hop")
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
