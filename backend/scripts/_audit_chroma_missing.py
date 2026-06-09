"""Full audit: active sqlite chunks missing from chroma."""

import sqlite3
from collections import defaultdict
from pathlib import Path

from app.core.chroma_client import get_collection

DB = Path(__file__).resolve().parents[2] / "data" / "knowledge_base.db"
BATCH = 100


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT c.knowledge_base_id, kb.name, c.id, d.filename, c.chunk_index
        FROM chunks c
        JOIN knowledge_bases kb ON kb.id = c.knowledge_base_id
        JOIN documents d ON d.id = c.document_id
        WHERE c.is_active = 1
        ORDER BY kb.name, d.filename, c.chunk_index
        """
    )
    rows = cur.fetchall()
    conn.close()

    by_kb: dict[str, list[tuple]] = defaultdict(list)
    for kb_id, kb_name, cid, fn, idx in rows:
        by_kb[kb_id].append((kb_name, cid, fn, idx))

    total_missing = 0
    docs_affected: dict[str, set[str]] = defaultdict(set)

    for kb_id, items in by_kb.items():
        col = get_collection(kb_id)
        missing_here = []
        for i in range(0, len(items), BATCH):
            batch = items[i : i + BATCH]
            ids = [x[1] for x in batch]
            got = set(col.get(ids=ids).get("ids") or [])
            for kb_name, cid, fn, idx in batch:
                if cid not in got:
                    missing_here.append((fn, idx, cid[:8]))
                    docs_affected[kb_name].add(fn)
        if missing_here:
            total_missing += len(missing_here)
            print(f"\n{items[0][0]!r}: {len(missing_here)} missing / {len(items)} active")
            for fn, idx, cid in missing_here[:10]:
                print(f"  {fn} #{idx} ({cid})")
            if len(missing_here) > 10:
                print(f"  ... +{len(missing_here) - 10} more")

    print("\n=== SUMMARY ===")
    print(f"Total active chunks: {len(rows)}")
    print(f"Missing from Chroma: {total_missing} ({100 * total_missing / max(1, len(rows)):.2f}%)")
    print(f"KBs with gaps: {len(docs_affected)}")
    for kb, docs in sorted(docs_affected.items()):
        print(f"  {kb!r}: {len(docs)} document(s)")


if __name__ == "__main__":
    main()
