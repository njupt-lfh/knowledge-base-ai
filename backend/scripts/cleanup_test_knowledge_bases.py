"""清理测试知识库

验证内容：
  - 按 ID 前缀/名称删除 pytest 残留库

运行方式（在 backend 目录）:
  python scripts/cleanup_test_knowledge_bases.py
  python scripts/cleanup_test_knowledge_bases.py --apply

预期结果：打印预览或删除结果并退出码 0。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import async_session, init_db
from app.models.knowledge_base import KnowledgeBase
from app.services.knowledge_service import KnowledgeService
from app.utils.test_kb import is_test_knowledge_base
from sqlalchemy import select


async def main(apply: bool) -> None:
    """预览或执行测试知识库清理。"""
    await init_db()
    async with async_session() as db:
        rows = (await db.execute(select(KnowledgeBase))).scalars().all()
        to_delete = [kb for kb in rows if is_test_knowledge_base(kb.id, kb.name)]
        keep = [kb for kb in rows if kb not in to_delete]

        print(f"总计 {len(rows)} 个知识库，拟删除测试库 {len(to_delete)} 个，保留 {len(keep)} 个")
        print("\n保留:")
        for kb in sorted(keep, key=lambda k: k.updated_at or k.created_at, reverse=True):
            print(f"  - {kb.name} ({kb.id})")

        if to_delete:
            print("\n拟删除:")
            for kb in to_delete:
                print(f"  - {kb.name} ({kb.id})")

        if not apply:
            print("\n预览模式，未删除。加 --apply 执行。")
            return

        svc = KnowledgeService(db)
        for kb in to_delete:
            await svc.delete(kb.id)
            print(f"deleted {kb.id} {kb.name}")

        print(f"\n已删除 {len(to_delete)} 个测试知识库。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="真正执行删除")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply))
