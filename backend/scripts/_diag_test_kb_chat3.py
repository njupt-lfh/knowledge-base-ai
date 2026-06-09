import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
KB_ID = "d42be3b3-b209-4ba2-b5ed-89e12fd1c9ae"
CHUNK_ID = "7bc302ed-57d1-48cf-9dc8-f321c9b12cf8"
QUERY = "标准普尔家庭资产象限图四个账户分别占多少比例"


async def main():
    from app.core.chroma_client import get_collection
    from app.core.database import async_session, init_db
    from app.services.crag_evaluator import evaluate_sufficiency
    from app.services.hybrid_retriever import HybridRetriever
    from app.services.query_router import route_query
    from app.services.rag_service import RAGService
    from app.services.retrieval_gate import apply_retrieval_abstention

    await init_db()

    col = get_collection(KB_ID)
    got = col.get(ids=[CHUNK_ID], include=["documents", "metadatas"])
    print("=== Chroma chunk 7bc302ed ===")
    print(" ids:", got.get("ids"))
    if got.get("documents"):
        print(" doc preview:", (got["documents"][0] or "")[:150])

    async with async_session() as db:
        route = route_query(QUERY)
        print("\n=== route:", route)

        hybrid = HybridRetriever()
        raw = await hybrid.retrieve(db, KB_ID, QUERY, top_k=15)
        print(f"\n=== hybrid raw n={len(raw)} ===")
        for i, s in enumerate(raw[:10], 1):
            hit = "<<" if s.get("chunk_id") == CHUNK_ID else ""
            print(
                f"{i}. {hit} score={s.get('score'):.4f} src={s.get('source')} "
                f"chunk={str(s.get('chunk_id', ''))[:8]} {(s.get('content') or '')[:70]}"
            )

        gated = apply_retrieval_abstention(QUERY, raw[:10], route)
        print(f"\n=== after abstention n={len(gated)} ===")
        for s in gated[:5]:
            print(f"  score={s.get('score')} {(s.get('content') or '')[:70]}")

        rag = RAGService()
        final = await rag.retrieve(KB_ID, QUERY, top_k=8, db=db)
        print(f"\n=== rag.retrieve final n={len(final)} ===")

        if raw:
            suff = evaluate_sufficiency(QUERY, raw[:8], route)
            print(
                f"\n=== CRAG sufficiency score={suff.score} sufficient={suff.sufficient} reason={suff.reason}"
            )


if __name__ == "__main__":
    asyncio.run(main())
