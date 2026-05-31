#!/usr/bin/env python3
"""将误存为 UUID 首段（8 位）的 kb_id / knowledge_base_id 修正为完整 UUID，并合并 Chroma 集合。"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "knowledge_base.db"

TABLES: list[tuple[str, str]] = [
    ("knowledge_gaps", "kb_id"),
    ("conversations", "knowledge_base_id"),
    ("documents", "knowledge_base_id"),
    ("chunks", "knowledge_base_id"),
    ("kg_relations", "knowledge_base_id"),
    ("knowledge_conflicts", "knowledge_base_id"),
    ("tags", "knowledge_base_id"),
    ("chunk_feedback", "kb_id"),
    ("kb_folder_watches", "knowledge_base_id"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="执行写入（默认仅预览）")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"DB not found: {DB_PATH}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    kbs = cur.execute("SELECT id FROM knowledge_bases").fetchall()
    mappings: dict[str, str] = {}
    for row in kbs:
        full = row["id"]
        prefix = full.split("-", 1)[0]
        if prefix != full and len(prefix) == 8:
            mappings[prefix] = full

    if not mappings:
        print("No prefix mappings to fix.")
        return 0

    print("Prefix → full UUID mappings:")
    for short, full in sorted(mappings.items()):
        print(f"  {short} → {full}")

    total = 0
    for table, col in TABLES:
        for short, full in mappings.items():
            n = cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} = ?", (short,)).fetchone()[0]
            if n:
                print(f"  {table}.{col}: {n} rows {short} → {full}")
                total += n
                if args.apply:
                    cur.execute(f"UPDATE {table} SET {col} = ? WHERE {col} = ?", (full, short))

    fts_n = 0
    for short, full in mappings.items():
        n = cur.execute(
            "SELECT COUNT(*) FROM chunks_fts WHERE knowledge_base_id = ?", (short,)
        ).fetchone()[0]
        if n:
            print(f"  chunks_fts.knowledge_base_id: {n} rows {short} → {full}")
            fts_n += n
            total += n
            if args.apply:
                cur.execute(
                    "UPDATE chunks_fts SET knowledge_base_id = ? WHERE knowledge_base_id = ?",
                    (full, short),
                )

    if args.apply:
        conn.commit()
        print(f"\nApplied SQL fixes ({total} row-updates).")
        try:
            from app.core.chroma_client import get_chroma_client

            client = get_chroma_client()
            for short, full in mappings.items():
                try:
                    short_col = client.get_collection(short)
                except Exception:
                    continue
                try:
                    full_col = client.get_collection(full)
                except Exception:
                    full_col = client.create_collection(
                        name=full, metadata={"hnsw:space": "cosine"}
                    )
                data = short_col.get(include=["embeddings", "documents", "metadatas"])
                ids = data.get("ids") or []
                if ids:
                    full_col.upsert(
                        ids=ids,
                        embeddings=data.get("embeddings"),
                        documents=data.get("documents"),
                        metadatas=data.get("metadatas"),
                    )
                    print(f"  Chroma: merged {len(ids)} vectors {short} → {full}")
                try:
                    client.delete_collection(short)
                except Exception:
                    pass
        except Exception as e:
            print(f"Chroma merge skipped or partial: {e}", file=sys.stderr)
    else:
        print(f"\nDry-run: {total} rows would be updated. Re-run with --apply to commit.")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
