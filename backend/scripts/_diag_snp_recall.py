"""Check vector/FTS recall for orig chunk."""

import asyncio

from app.core.database import async_session, init_db
from app.services.fts_service import search_fts
from app.services.hybrid_retriever import HybridRetriever

QUERY = "标准普尔家庭资产配置是什么？"
KB = "d189f251-08c4-4e18-8d3d-0e9639b7f6ff"
ORIG = "c6f567e4-7c33-4e37-b906-6728904a464f"


async def main() -> None:
    await init_db()
    async with async_session() as db:
        h = HybridRetriever()
        fts = await search_fts(db, KB, QUERY, limit=30)
        print(f"FTS hits: {len(fts)}")
        for i, (cid, score) in enumerate(fts[:10]):
            mark = " ORIG" if cid == ORIG else ""
            print(f"  {i} {cid[:8]} bm25={score:.4f}{mark}")

        vec = await h.vector_only_search(db, KB, QUERY, top_k=15)
        print(f"\nVector hits: {len(vec)}")
        for i, s in enumerate(vec[:10]):
            mark = " ORIG" if s["chunk_id"] == ORIG else ""
            print(f"  {i} {s['chunk_id'][:8]} score={s['score']}{mark}")

        # direct check orig in chroma
        from app.core.chroma_client import get_collection

        col = get_collection(KB)
        got = col.get(ids=[ORIG])
        print(f"\nChroma has orig chunk: {bool(got and got.get('ids'))}")


if __name__ == "__main__":
    asyncio.run(main())
