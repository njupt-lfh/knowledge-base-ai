import asyncio
import sqlite3
from pathlib import Path

from app.services.fts_service import build_fts_query

DB = Path(__file__).resolve().parents[2] / "data" / "knowledge_base.db"
QUERY = "标准普尔家庭资产配置是什么？"
KB = "d189f251-08c4-4e18-8d3d-0e9639b7f6ff"
ORIG = "c6f567e4-7c33-4e37-b906-6728904a464f"


async def async_fts():
    from app.core.database import async_session, init_db
    from app.services.fts_service import search_fts

    await init_db()
    async with async_session() as db:
        hits = await search_fts(db, KB, QUERY, limit=30)
        print("async fts hits:", len(hits))
        for cid, score in hits[:10]:
            mark = " ORIG" if cid == ORIG else ""
            print(cid[:8], score, mark)


def sync_fts():
    match = build_fts_query(QUERY)
    print("match:", match)
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT f.chunk_id, bm25(chunks_fts) AS bm
        FROM chunks_fts f
        INNER JOIN chunks c ON c.id = f.chunk_id
        WHERE chunks_fts MATCH ?
          AND f.knowledge_base_id = ?
          AND c.is_active = 1
        ORDER BY bm
        LIMIT 15
        """,
        (match, KB),
    )
    rows = cur.fetchall()
    print("sync hits:", len(rows))
    for cid, score in rows:
        mark = " ORIG" if cid == ORIG else ""
        print(cid[:8], score, mark)
    conn.close()


if __name__ == "__main__":
    sync_fts()
    asyncio.run(async_fts())
