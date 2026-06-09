import asyncio
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
DB = ROOT / "data" / "knowledge_base.db"
KB_ID = "d42be3b3-b209-4ba2-b5ed-89e12fd1c9ae"
QUERY = "标准普尔家庭资产象限图四个账户分别占多少比例"


def main_sql():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    print("=== latest msgs ===")
    for r in c.execute(
        """
        SELECT m.role, m.content, m.created_at
        FROM messages m
        JOIN conversations cv ON cv.id = m.conversation_id
        WHERE cv.knowledge_base_id = ?
        ORDER BY m.created_at DESC LIMIT 4
        """,
        (KB_ID,),
    ):
        print(r["created_at"], r["role"], (r["content"] or "")[:120])

    print("\n=== chunks with 标准普尔 ===")
    for r in c.execute(
        """
        SELECT ch.id, d.filename, substr(ch.content,1,150) AS preview
        FROM chunks ch
        JOIN documents d ON d.id = ch.document_id
        WHERE ch.knowledge_base_id = ? AND ch.is_active = 1 AND ch.content LIKE '%标准普尔%'
        """,
        (KB_ID,),
    ):
        print(r["id"], r["filename"])
        print(" ", r["preview"])

    print("\n=== 06-理财规划篇 doc/chunks ===")
    for r in c.execute(
        """
        SELECT d.id, d.filename, d.status, d.chunk_count,
               (SELECT COUNT(*) FROM chunks c WHERE c.document_id=d.id AND c.is_active=1) AS active_chunks
        FROM documents d
        WHERE d.knowledge_base_id = ? AND d.filename LIKE '%理财%'
        """,
        (KB_ID,),
    ):
        print(dict(r))

    for r in c.execute(
        """
        SELECT ch.id, ch.chunk_index, length(ch.content) AS len, substr(ch.content,1,200) AS preview
        FROM chunks ch
        JOIN documents d ON d.id = ch.document_id
        WHERE d.filename LIKE '%06-理财%' AND ch.knowledge_base_id = ?
        ORDER BY ch.chunk_index
        """,
        (KB_ID,),
    ):
        print(" chunk", r["chunk_index"], r["id"], "len=", r["len"])
        print(" ", r["preview"][:180])

    print("\n=== [Gap] doc ===")
    for r in c.execute(
        """
        SELECT ch.id, substr(ch.content,1,300) FROM chunks ch
        JOIN documents d ON d.id = ch.document_id
        WHERE d.filename LIKE '[Gap]%' AND ch.knowledge_base_id = ?
        """,
        (KB_ID,),
    ):
        print(r[0], r[1][:200])

    c.close()


async def main_rag():
    from app.core.database import async_session, init_db
    from app.services.hybrid_retriever import HybridRetriever
    from app.services.query_router import classify_query_route
    from app.services.rag_service import RAGService
    from app.services.retrieval_gate import apply_retrieval_abstention

    query = QUERY
    await init_db()
    async with async_session() as db:
        route = classify_query_route(query)
        print("\n=== route ===", route)

        hybrid = HybridRetriever()
        raw = await hybrid.retrieve(db, KB_ID, query, top_k=15)
        print(f"\n=== hybrid raw top={len(raw)} ===")
        for i, s in enumerate(raw[:8], 1):
            print(
                f"{i}. score={s.get('score'):.4f} src={s.get('source')} {(s.get('content') or '')[:80]}"
            )

        rag = RAGService()
        final = await rag.retrieve(KB_ID, query, top_k=8, db=db)
        print(f"\n=== rag.retrieve final top={len(final)} ===")
        for i, s in enumerate(final[:5], 1):
            print(
                f"{i}. score={s.get('score')} ce={s.get('cross_encoder_score')} {(s.get('content') or '')[:80]}"
            )

        gated = apply_retrieval_abstention(query, raw[:8], route)
        print(f"\n=== after abstention gate: {len(gated)} ===")


if __name__ == "__main__":
    main_sql()
    asyncio.run(main_rag())
