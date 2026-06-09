"""Simulate pre-gap state: deactivate gap chunk temporarily."""

import asyncio

from app.core import chat_runtime as rt
from app.core.database import async_session, init_db
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.crag_evaluator import evaluate_sufficiency
from app.services.cross_encoder_rerank_service import cross_encoder_rerank
from app.services.query_router import route_query
from app.services.retrieval_gate import apply_retrieval_abstention

QUERY = "标准普尔家庭资产配置是什么？"
KB = "d189f251-08c4-4e18-8d3d-0e9639b7f6ff"
ORIG = "c6f567e4-7c33-4e37-b906-6728904a464f"
GAP = "ea79d24e-f3e4-4b78-bebb-decbc2435c36"


async def rank_check(db, orch, route):
    raw = await orch.hybrid.search(db, KB, QUERY, top_k=30, allow_soft_fallback=True)
    print(f"\nRaw hybrid pool (pre-CE filter): {len(raw)}")
    for i, s in enumerate(raw[:8]):
        mark = ""
        cid = s.get("chunk_id", "")
        if cid == ORIG:
            mark = " <-- ORIG"
        elif cid == GAP:
            mark = " <-- GAP"
        print(f"  {i} {cid[:8]} score={s.get('score')} {mark} {(s.get('content') or '')[:45]}")

    ce = cross_encoder_rerank(QUERY, raw, top_k=min(len(raw), 30))
    print(f"\nAfter CE rerank: {len(ce)}")
    for i, s in enumerate(ce[:8]):
        mark = ""
        cid = s.get("chunk_id", "")
        if cid == ORIG:
            mark = " <-- ORIG"
        elif cid == GAP:
            mark = " <-- GAP"
        print(f"  {i} {cid[:8]} ce={s.get('cross_encoder_score')} score={s.get('score')} {mark}")

    gated = apply_retrieval_abstention(QUERY, ce[:5], route)
    ev = evaluate_sufficiency(QUERY, gated, route)
    print(
        f"\nTop5 after CE -> abstention: {len(gated)} sufficient={ev.sufficient} reason={ev.reason}"
    )


async def run_with_gap_active(active: bool, fast: bool) -> None:
    from app.models.chunk import Chunk

    async with async_session() as db:
        gap = await db.get(Chunk, GAP)
        if gap:
            gap.is_active = active
        await db.commit()

        with rt.fast_mode_context(fast):
            orch = AgentOrchestrator()
            route = route_query(QUERY)
            await rank_check(db, orch, route)
            run = await orch.run(db, KB, QUERY)
            print(
                f"\nrun(fast={fast}, gap_active={active}): refused={run.refused} "
                f"sufficient={run.sufficient} sources={len(run.sources)} rounds={run.rounds}"
            )
            if run.sufficiency:
                s = run.sufficiency
                print(
                    f"  crag reason={s.reason} max={s.max_retrieval_score} overlap={s.substantive_overlap}"
                )
            for i, src in enumerate(run.sources[:3]):
                print(f"  [{i}] {src.get('chunk_id', '')[:8]} ce={src.get('cross_encoder_score')}")

        if gap:
            gap.is_active = True
        await db.commit()


async def main() -> None:
    await init_db()
    print("=== PRE-GAP SIMULATION (gap chunk deactivated) ===")
    await run_with_gap_active(active=False, fast=False)
    print("\n=== FAST MODE PRE-GAP ===")
    await run_with_gap_active(active=False, fast=True)


if __name__ == "__main__":
    asyncio.run(main())
