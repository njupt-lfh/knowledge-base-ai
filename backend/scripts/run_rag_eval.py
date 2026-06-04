"""Phase 0 RAG 评测：检索指标 + RAGAS / LLM Judge + 生成评测

用法（在 backend 目录）:
  python scripts/run_rag_eval.py                    # 全量 20×N 样本（默认无 limit）
  python scripts/run_rag_eval.py --retrieval-only
  python scripts/run_rag_eval.py --ragas --llm-judge
  python scripts/run_rag_eval.py --deepeval         # DeepEval 指标 + retention

输出: ../data/eval_baseline_report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

DATA_FILE = ROOT / "data" / "eval_qa_dataset.json"
REPORT_FILE = ROOT / "data" / "eval_baseline_report.json"

from app.eval.deepeval_runner import check_knowledge_retention, run_deepeval  # noqa: E402
from app.eval.ragas_runner import llm_judge_faithfulness, run_ragas_eval  # noqa: E402
from app.eval.retrieval_metrics import retrieval_metrics  # noqa: E402


async def _collect_generation(
    rag: Any, kb_id: str, question: str, top_k: int, db: Any
) -> tuple[str, list[dict]]:
    answer_parts: list[str] = []
    sources: list[dict] = []
    async for event in rag.generate(kb_id, question, [], top_k, db):
        if not event.startswith("data: "):
            continue
        payload = json.loads(event[6:].strip())
        if payload.get("type") == "text":
            answer_parts.append(payload.get("content", ""))
        elif payload.get("type") == "sources":
            sources = payload.get("sources", [])
    return "".join(answer_parts), sources


def _diagnose(agg: dict[str, Any], *, has_generation: bool) -> dict[str, str]:
    cr = agg.get("context_recall_mean")
    cp = agg.get("context_precision_mean")
    fr = agg.get("faithfulness_mean") or agg.get("llm_judge_faithfulness_mean")
    neg_rate = agg.get("negative_reject_rate")

    retrieval_weak = cr is not None and cr < 0.6
    precision_weak = cp is not None and cp < 0.35
    generation_weak = fr is not None and fr < 0.6
    reject_weak = neg_rate is not None and neg_rate < 0.5

    if not has_generation:
        if retrieval_weak:
            return {
                "primary_bottleneck": "retrieval",
                "recommendation": "相关 chunk 召回不足，优先 Hybrid/Rerank/分块。",
            }
        return {
            "primary_bottleneck": "retrieval_baseline_only",
            "recommendation": (
                "本报告为检索专项基线（--retrieval-only），已包含召回率/命中率等指标；"
                "忠实度与答案相关性需另跑完整评测：python scripts/run_rag_eval.py --ragas --llm-judge"
            ),
        }

    if retrieval_weak and (generation_weak or reject_weak):
        return {
            "primary_bottleneck": "both",
            "recommendation": "检索与生成/拒答均偏弱，先修检索与负例拒答。",
        }
    if retrieval_weak or precision_weak:
        return {
            "primary_bottleneck": "retrieval",
            "recommendation": f"context_recall={cr}、precision={cp}：优先 Hybrid/Rerank/分块。",
        }
    if reject_weak:
        return {
            "primary_bottleneck": "generation",
            "recommendation": f"负例拒答率 {neg_rate} 偏低，优化 Prompt/CRAG。",
        }
    if generation_weak:
        return {
            "primary_bottleneck": "generation",
            "recommendation": "忠实度/相关性偏低，优化 Prompt 与引用约束。",
        }
    return {"primary_bottleneck": "balanced", "recommendation": "指标未明显偏向，请逐条复核报告。"}


def _aggregate(samples: list[dict]) -> dict[str, Any]:
    def _avg(key: str) -> float | None:
        vals = [s[key] for s in samples if s.get(key) is not None]
        return round(mean(vals), 4) if vals else None

    non_neg = [s for s in samples if s.get("q_type") != "negative"]
    neg = [s for s in samples if s.get("q_type") == "negative"]

    return {
        "sample_count": len(samples),
        "context_recall_mean": _avg("context_recall"),
        "context_precision_mean": _avg("context_precision"),
        "retrieval_hit_rate": round(
            mean(1.0 if s.get("retrieval_hit") else 0.0 for s in non_neg), 4
        )
        if non_neg
        else None,
        "negative_reject_rate": round(mean(1.0 if s.get("negative_ok") else 0.0 for s in neg), 4)
        if neg
        else None,
        "faithfulness_mean": _avg("faithfulness"),
        "answer_relevancy_mean": _avg("answer_relevancy"),
        "llm_judge_faithfulness_mean": _avg("llm_judge_faithfulness"),
        "avg_retrieve_ms": _avg("retrieve_ms"),
        "avg_generate_ms": _avg("generate_ms"),
    }


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


async def _run(args: argparse.Namespace) -> int:
    from app.core.config import settings
    from app.core.database import async_session
    from app.services.agent_orchestrator import AgentOrchestrator
    from app.services.rag_service import RAGService

    if not DATA_FILE.exists():
        print(f"FAIL: missing {DATA_FILE}")
        return 1

    if settings.LLM_MOCK_MODE and not args.retrieval_only:
        print("FAIL: LLM_MOCK_MODE=true，评测需真实 API")
        return 1

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    samples = data["samples"]
    if args.limit > 0:
        samples = samples[: args.limit]

    baseline_before: dict[str, Any] | None = None
    if REPORT_FILE.exists():
        try:
            baseline_before = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            baseline_before = None

    agent = AgentOrchestrator()
    rag = RAGService()
    results: list[dict] = []

    print(
        f"Evaluating {len(samples)} samples (top_k={args.top_k}, ragas={args.ragas}, llm_judge={args.llm_judge})"
    )

    async with async_session() as db:
        for s in samples:
            kb_id = s["kb_id"]
            question = s["question"]
            relevant = {x for x in (s.get("relevant_chunk_ids") or []) if x}

            t0 = time.perf_counter()
            sources, _route, _paths = await agent.retrieve_for_eval(
                db, kb_id, question, top_k=args.top_k
            )
            retrieve_ms = round((time.perf_counter() - t0) * 1000, 1)

            retrieved_ids = [x["chunk_id"] for x in sources]
            metrics = retrieval_metrics(relevant, retrieved_ids, s["q_type"])

            answer = ""
            generate_ms = None
            contexts = [x["content"] for x in sources]

            if not args.retrieval_only:
                t1 = time.perf_counter()
                answer, sources = await _collect_generation(rag, kb_id, question, args.top_k, db)
                generate_ms = round((time.perf_counter() - t1) * 1000, 1)
                contexts = [x["content"] for x in sources]
                retrieved_ids = [x["chunk_id"] for x in sources]
                metrics = retrieval_metrics(relevant, retrieved_ids, s["q_type"])

            row = {
                "id": s["id"],
                "kb_id": kb_id,
                "q_type": s["q_type"],
                "question": question,
                "ground_truth": s.get("ground_truth", ""),
                "answer": answer,
                "contexts": contexts,
                "retrieved_chunk_ids": retrieved_ids,
                "retrieve_ms": retrieve_ms,
                "generate_ms": generate_ms,
                **metrics,
            }
            results.append(row)
            print(
                f"  {s['id']} recall={metrics.get('context_recall')} hit={metrics.get('retrieval_hit')}"
            )

    agg = _aggregate(results)
    ragas_meta: dict[str, Any] = {}

    if args.ragas and not args.retrieval_only:
        ragas_meta = run_ragas_eval(results)
        scores = ragas_meta.get("scores") or {}
        agg["ragas"] = scores
        agg["ragas_errors"] = ragas_meta.get("errors", [])
        for key in ("faithfulness", "answer_relevancy", "context_precision", "context_recall"):
            if scores.get(key) is not None:
                if key == "faithfulness":
                    agg["faithfulness_mean"] = scores[key]
                elif key == "answer_relevancy":
                    agg["answer_relevancy_mean"] = scores[key]

    if args.llm_judge and not args.retrieval_only:
        judge_scores: list[float] = []
        for r in results:
            if r.get("q_type") == "negative" or not r.get("answer"):
                continue
            sc = await llm_judge_faithfulness(
                r["question"], r["answer"], r.get("contexts") or [], r.get("ground_truth", "")
            )
            if sc is not None:
                r["llm_judge_faithfulness"] = sc
                judge_scores.append(sc)
        if judge_scores:
            agg["llm_judge_faithfulness_mean"] = round(mean(judge_scores), 4)
        if agg.get("faithfulness_mean") is None and judge_scores:
            agg["faithfulness_mean"] = agg["llm_judge_faithfulness_mean"]

    deepeval_meta: dict[str, Any] = {}
    retention_meta: dict[str, Any] = {"skipped": True}

    if args.deepeval and not args.retrieval_only:
        deepeval_meta = run_deepeval(results, prefer_live=not settings.LLM_MOCK_MODE)
        agg["deepeval"] = {
            "hallucination_mean": deepeval_meta.get("hallucination_mean"),
            "contextual_relevancy_mean": deepeval_meta.get("contextual_relevancy_mean"),
            "mode": deepeval_meta.get("mode"),
        }
        if (
            deepeval_meta.get("hallucination_mean") is not None
            and agg.get("faithfulness_mean") is None
        ):
            agg["faithfulness_mean"] = deepeval_meta["hallucination_mean"]

    if args.deepeval and baseline_before and agg.get("context_recall_mean") is not None:
        retention_meta = check_knowledge_retention(
            baseline_before.get("aggregate") or {},
            agg,
            min_recall_ratio=args.min_recall_ratio,
        )
        retention_meta["skipped"] = False

    diagnosis = _diagnose(agg, has_generation=not args.retrieval_only)

    report = {
        "version": "2.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "primary_kb_id": data.get("primary_kb_id"),
        "knowledge_bases": data.get("knowledge_bases"),
        "config": {
            "top_k": args.top_k,
            "retrieval_only": args.retrieval_only,
            "eval_mode": "retrieval_only" if args.retrieval_only else "full",
            "ragas_enabled": args.ragas,
            "llm_judge_enabled": args.llm_judge,
            "deepeval_enabled": args.deepeval,
            "llm_mock_mode": settings.LLM_MOCK_MODE,
            "limit": args.limit,
            "sample_count": len(samples),
        },
        "aggregate": agg,
        "ragas_run": ragas_meta,
        "deepeval_run": deepeval_meta,
        "knowledge_retention": retention_meta,
        "diagnosis": diagnosis,
        "samples": results,
    }

    REPORT_FILE.write_text(
        json.dumps(_json_safe(report), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 写入 eval_runs，供评测基线页「历史趋势」使用（与 JSON 基线同步）
    async with async_session() as db:
        from app.services.eval_run_service import persist_eval_report

        run_id = await persist_eval_report(db, report, ci_phase="rag_eval")
    print(f"  eval_run persisted -> {run_id}")

    print(f"\nPASS: report -> {REPORT_FILE}")
    print(f"  context_recall_mean: {agg.get('context_recall_mean')}")
    print(f"  faithfulness_mean:   {agg.get('faithfulness_mean')}")
    print(f"  diagnosis: {diagnosis['primary_bottleneck']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run RAG eval baseline (Phase 0)")
    parser.add_argument("--limit", type=int, default=0, help="0 = all samples")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument("--ragas", action="store_true")
    parser.add_argument("--llm-judge", action="store_true", help="LLM 忠实度回退/补充")
    parser.add_argument(
        "--deepeval", action="store_true", help="DeepEval Hallucination + Contextual Relevancy"
    )
    parser.add_argument(
        "--min-recall-ratio", type=float, default=0.85, help="Knowledge retention 门禁"
    )
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
