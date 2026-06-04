"""确保 SQLite ORM 表完整

验证内容：
  - init_db 补齐缺失表

运行方式（在 backend 目录）:
  python scripts/ensure_db_schema.py

预期结果：打印 PASS 并退出码 0；失败时退出码 1（部分脚本 SKIP 为 0）。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


async def main() -> int:
    """初始化数据库并校验全部 ORM 表是否齐全。"""
    from app.core.database import existing_table_names, expected_table_names, init_db, verify_schema

    before = await existing_table_names()
    print(f"Before: {len(before)} tables")

    await init_db()

    after = await existing_table_names()
    expected = expected_table_names()
    missing = await verify_schema()

    # 打印期望表与实际表对比
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
