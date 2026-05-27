"""Phase 2.1 验收：Hybrid 检索 + FTS5 + RRF"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


async def main() -> int:
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select, text

    from app.core.database import async_session, init_db
    from app.main import app
    from app.models.knowledge_base import KnowledgeBase
    from app.services.hybrid_retriever import reciprocal_rank_fusion
    from app.services.rerank_service import rerank_candidates

    await init_db()

    async with async_session() as db:
        row = (
            await db.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_fts'")
            )
        ).first()
        if not row:
            print("FAIL: chunks_fts not found")
            return 1

        kb = (await db.execute(select(KnowledgeBase).limit(1))).scalar_one_or_none()
        if kb:
            from app.services.hybrid_retriever import HybridRetriever

            retriever = HybridRetriever()
            hits = await retriever.search(db, kb.id, "RAG 检索", top_k=3)
            print(f"  hybrid search hits={len(hits)}")

    rrf = reciprocal_rank_fusion([["a", "b"], ["b", "c"]])
    if rrf.get("b", 0) <= rrf.get("a", 0):
        print(f"FAIL: RRF merge unexpected {rrf}")
        return 1

    reranked = rerank_candidates("python 环境变量", [{"content": "dotenv 读取环境变量", "rrf_score": 0.5}], top_k=1)
    if not reranked:
        print("FAIL: rerank empty")
        return 1

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        if kb:
            res = await client.post(
                f"/api/knowledge-bases/{kb.id}/search",
                json={"query": "test", "top_k": 3},
            )
            if res.status_code != 200:
                print(f"FAIL: search API {res.status_code}")
                return 1

    print("PASS: Phase 2.1 — FTS5 + Hybrid + RRF + Rerank")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
