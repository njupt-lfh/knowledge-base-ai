"""确保 SQLite 中存在全部 ORM 表（可独立运行，不依赖 uvicorn 启动）

用法（在 backend 目录）:
  python scripts/ensure_db_schema.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


async def main() -> int:
    from app.core.database import existing_table_names, expected_table_names, init_db, verify_schema

    before = await existing_table_names()
    print(f"Before: {len(before)} tables")

    await init_db()

    after = await existing_table_names()
    expected = expected_table_names()
    missing = await verify_schema()

    print(f"Expected ({len(expected)}): {', '.join(sorted(expected))}")
    print(f"After ({len(after)}): {', '.join(sorted(after))}")

    if missing:
        print(f"FAIL: still missing {missing}")
        return 1

    created = sorted(expected - before)
    if created:
        print(f"PASS: created tables: {', '.join(created)}")
    else:
        print("PASS: schema already complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
