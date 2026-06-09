"""Compare SQLite active chunks vs Chroma indexed ids (read-only audit)."""

import asyncio
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "knowledge_base.db"


def sqlite_stats():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT kb.id, kb.name, COUNT(c.id)
        FROM knowledge_bases kb
        LEFT JOIN chunks c ON c.knowledge_base_id = kb.id AND c.is_active = 1
        GROUP BY kb.id, kb.name
        ORDER BY kb.name
        """
    )
    rows = cur.fetchall()
    conn.close()
    return rows


async def chroma_stats():
    from app.core.chroma_client import get_collection

    out = []
    for kb_id, name, sqlite_n in sqlite_stats():
        try:
            col = get_collection(kb_id)
            chroma_n = col.count()
        except Exception as e:
            chroma_n = -1
            err = str(e)
        else:
            err = ""
        out.append((name, kb_id[:8], sqlite_n, chroma_n, err))
    return out


async def sample_missing(kb_id: str, kb_name: str, sample: int = 200):
    from app.core.chroma_client import get_collection

    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM chunks WHERE knowledge_base_id=? AND is_active=1 LIMIT ?",
        (kb_id, sample),
    )
    ids = [r[0] for r in cur.fetchall()]
    conn.close()
    if not ids:
        return 0, 0
    col = get_collection(kb_id)
    got = col.get(ids=ids)
    present = len(got.get("ids") or [])
    return len(ids), present


async def main():
    print("=== SQLite vs Chroma counts ===")
    stats = await chroma_stats()
    total_sqlite = total_chroma = 0
    for name, _kid, sqlite_n, chroma_n, err in stats:
        total_sqlite += sqlite_n
        if chroma_n >= 0:
            total_chroma += chroma_n
        gap = "" if chroma_n < 0 else f" delta={chroma_n - sqlite_n:+d}"
        print(f"  {name!r}: sqlite={sqlite_n} chroma={chroma_n}{gap} {err}")
    print(
        f"  TOTAL: sqlite={total_sqlite} chroma={total_chroma} delta={total_chroma - total_sqlite:+d}"
    )

    print("\n=== Sample missing-in-chroma (first 200 active chunks per KB) ===")
    for kb_id, name, _ in sqlite_stats():
        n, present = await sample_missing(kb_id, name, 200)
        if n:
            print(f"  {name!r}: present {present}/{n} ({100 * present / n:.1f}%)")

    # spot-check finance orig chunk
    ORIG = "c6f567e4-7c33-4e37-b906-6728904a464f"
    from app.core.chroma_client import get_collection

    kb = "d189f251-08c4-4e18-8d3d-0e9639b7f6ff"
    col = get_collection(kb)
    print(f"\nSpot check orig chunk in chroma: {bool(col.get(ids=[ORIG]).get('ids'))}")


if __name__ == "__main__":
    asyncio.run(main())
