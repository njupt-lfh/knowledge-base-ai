import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
KB_ID = "d42be3b3-b209-4ba2-b5ed-89e12fd1c9ae"
CHUNK_ID = "7bc302ed-57d1-48cf-9dc8-f321c9b12cf8"
QUERY = "标准普尔家庭资产象限图四个账户分别占多少比例"


async def main():
    from app.core.database import async_session, init_db
    from app.services.agent_orchestrator import AgentOrchestrator
    from app.services.crag_evaluator import evaluate_sufficiency
    from app.services.hybrid_retriever import HybridRetriever
    from app.services.query_router import route_query
    from app.services.retrieval_gate import apply_retrieval_abstention

    await init_db()
    route = route_query(QUERY)
    hybrid = HybridRetriever()

    async with async_session() as db:
        vec = await hybrid._vector_search(KB_ID, QUERY, 30)
        from app.services.fts_service import search_fts

        fts = await search_fts(db, KB_ID, QUERY, limit=30)
        fts_ids = [x[0] for x in fts]
        print("=== vector ids", len(vec), "target in vec:", CHUNK_ID in vec)
        print("=== fts ids", len(fts_ids), "target in fts:", CHUNK_ID in fts_ids)
        if CHUNK_ID in vec:
            print("  vector rank:", vec.index(CHUNK_ID) + 1)
        if CHUNK_ID in fts_ids:
            print("  fts rank:", fts_ids.index(CHUNK_ID) + 1)

        raw_hybrid = await hybrid.search(db, KB_ID, QUERY, top_k=15, allow_soft_fallback=True)
        print(f"\n=== hybrid.search n={len(raw_hybrid)} ===")
        for i, s in enumerate(raw_hybrid[:8], 1):
            mark = "<<" if s.get("chunk_id") == CHUNK_ID else ""
            print(
                f"{i}. {mark} score={s.get('score')} q={s.get('quality_score')} {(s.get('content') or '')[:60]}"
            )

        abst = apply_retrieval_abstention(QUERY, raw_hybrid, route)
        print(f"\n=== after abstention n={len(abst)} ===")

        orch = AgentOrchestrator()
        run = await orch.run(db, KB_ID, QUERY, history=[])
        print("\n=== agent run ===")
        print(f" refused={run.refused} sufficient={run.sufficient} rounds={run.rounds}")
        print(
            f" sources={len(run.sources)} crag_score={run.sufficiency.score if run.sufficiency else None}"
        )
        print(f" crag_reason={run.sufficiency.reason if run.sufficiency else ''}")
        if run.sources:
            for i, s in enumerate(run.sources[:3], 1):
                print(f"  {i}. score={s.get('score')} {(s.get('content') or '')[:60]}")

        if raw_hybrid:
            ev = evaluate_sufficiency(QUERY, raw_hybrid, route)
            print(
                f"\n=== CRAG on hybrid raw: sufficient={ev.sufficient} score={ev.score} reason={ev.reason}"
            )


if __name__ == "__main__":
    asyncio.run(main())
