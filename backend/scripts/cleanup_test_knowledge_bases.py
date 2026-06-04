"""清理测试知识库

验证内容：
  - 按 ID 前缀/名称删除 pytest 残留库

运行方式（在 backend 目录）:
  python scripts/cleanup_test_knowledge_bases.py

预期结果：打印 PASS 并退出码 0；失败时退出码 1（部分脚本 SKIP 为 0）。
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
from sqlalchemy import select

TEST_ID_PREFIXES = (
    "kb-toggle-",
    "kb-upload-",
    "kb-manual-",
    "kb-doc-fts-",
    "kb-inc-",
    "kb-sync-api-",
    "kb-sync-",
    "kb-p42-",
    "kb-p43-",
    "kb-p44-",
    "kb-t4-",
    "kb-graph-",
    "kb-gr-",
    "kb-fts-",
    "kb-verify-",
    "kb-smoke-",
    "kb-dbg",
    "kb-p4-",
    "kb-p3-",
)

TEST_NAMES = {
    "t",
    "g",
    "inc",
    "sync",
    "sync-api",
    "fts-test",
    "toggle-kb",
    "upload-kb",
    "manual-kb",
    "p43",
    "p44",
    "p4",
    "p3",
    "fts-verify",
    "x",
}


def is_test_kb(kb: KnowledgeBase) -> bool:
    """根据 ID 前缀或名称判断是否为测试知识库。"""
    if any(kb.id.startswith(p) for p in TEST_ID_PREFIXES):
        return True
    if kb.name in TEST_NAMES:
        return True
    if kb.name and kb.name.startswith("PDF联调-"):
        return True
    if kb.name and kb.name.startswith("图片联调-"):
        return True
    return False


async def main(apply: bool) -> None:
    """预览或执行测试知识库清理。"""
    await init_db()
    async with async_session() as db:
        rows = (await db.execute(select(KnowledgeBase))).scalars().all()
        to_delete = [kb for kb in rows if is_test_kb(kb)]
        keep = [kb for kb in rows if kb not in to_delete]

        print(f"总计 {len(rows)} 个知识库，拟删除测试库 {len(to_delete)} 个，保留 {len(keep)} 个")
        print("\n保留:")
        for kb in sorted(keep, key=lambda k: k.updated_at or k.created_at, reverse=True):
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
