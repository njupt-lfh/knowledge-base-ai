"""Diagnose 标准普尔 retrieval paths."""

import asyncio

from app.core import chat_runtime as rt
from app.core.database import async_session, init_db
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.crag_evaluator import evaluate_sufficiency
from app.services.query_router import route_query
from app.services.retrieval_gate import apply_retrieval_abstention

QUERY = "标准普尔家庭资产配置是什么？"
KB = "d189f251-08c4-4e18-8d3d-0e9639b7f6ff"
ORIG = "c6f567e4-7c33-4e37-b906-6728904a464f"
GAP = "ea79d24e-f3e4-4b78-bebb-decbc2435c36"


async def probe(label: str, *, fast: bool, filter_gap: bool) -> None:
    with rt.fast_mode_context(fast):
        async with async_session() as db:
            orch = AgentOrchestrator()
            route = route_query(QUERY)
            hybrid = await orch.hybrid.search(db, KB, QUERY, top_k=10)
            if filter_gap:
                hybrid = [h for h in hybrid if h.get("chunk_id") != GAP]
            gated = apply_retrieval_abstention(QUERY, hybrid, route)
            ev = evaluate_sufficiency(QUERY, gated, route)
            run = await orch.run(db, KB, QUERY)
            print(f"\n=== {label} (fast={fast}, filter_gap={filter_gap}) ===")
            print(
                f"hybrid={len(hybrid)} gated={len(gated)} "
                f"crag={ev.sufficient}/{ev.reason} max={ev.max_retrieval_score:.4f} overlap={ev.substantive_overlap:.4f}"
            )
            print(
                f"run refused={run.refused} sufficient={run.sufficient} "
                f"sources={len(run.sources)} rounds={run.rounds}"
            )
            ids = {ORIG[:8]: False, GAP[:8]: False}
            for s in run.sources:
                cid = s.get("chunk_id", "")
                if cid == ORIG:
                    ids[ORIG[:8]] = True
                if cid == GAP:
                    ids[GAP[:8]] = True
            print(f"has orig={ids[ORIG[:8]]} has gap={ids[GAP[:8]]}")
            for i, s in enumerate(run.sources[:3]):
                cid = s.get("chunk_id", "")[:8]
                preview = (s.get("content") or "")[:55].replace("\n", " ")
                print(
                    f"  [{i}] {cid} score={s.get('score')} ce={s.get('cross_encoder_score')} {preview!r}"
                )


async def main() -> None:
    await init_db()
    await probe("normal", fast=False, filter_gap=False)
    await probe("normal without gap in hybrid pool", fast=False, filter_gap=True)
    await probe("fast", fast=True, filter_gap=False)


if __name__ == "__main__":
    asyncio.run(main())
