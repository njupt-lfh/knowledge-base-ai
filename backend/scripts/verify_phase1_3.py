"""Phase 1.3 验收：治理扫描 + 治理动作 API。

验证内容：
  - GovernanceService.scan_suggestions 返回 health 与 suggestions
  - apply_action 可 deactivate/archive chunk 并恢复
  - 治理 REST API 可正常响应

运行方式（在 backend 目录）:
  python scripts/verify_phase1_3.py

预期结果：打印 PASS 并退出码 0；无知识库时 SKIP 退出码 0。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


async def main() -> int:
    """执行 Phase 1.3 验收：治理扫描、动作应用与 API。"""
    from app.core.database import async_session, init_db
    from app.main import app
    from app.models.chunk import Chunk
    from app.models.knowledge_base import KnowledgeBase
    from app.services.governance_service import GovernanceService
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select

    await init_db()

    async with async_session() as db:
        kb = (await db.execute(select(KnowledgeBase).limit(1))).scalar_one_or_none()

        if not kb:
            print("SKIP: no knowledge base in DB")
            return 0

        svc = GovernanceService(db)

        # 验证治理扫描返回结构
        scan = await svc.scan_suggestions(kb.id, scan_duplicates=False)
        if "health" not in scan or "suggestions" not in scan:
            print("FAIL: scan_suggestions missing keys")
            return 1

        print(
            f"  suggestions={len(scan['suggestions'])}, cold_90d={scan['health'].get('cold_count_90d')}"
        )

        chunk = (
            await db.execute(select(Chunk).where(Chunk.knowledge_base_id == kb.id).limit(1))
        ).scalar_one_or_none()

        if chunk and chunk.is_active:
            # 验证 deactivate 动作
            result = await svc.apply_action(kb.id, "deactivate", [chunk.id])
            if result.get("applied", 0) < 1:
                print("FAIL: apply_action deactivate")
                return 1

            # 验证 archive 动作使 chunk 变为 inactive
            await svc.apply_action(kb.id, "archive", [chunk.id])
            chunk2 = await db.get(Chunk, chunk.id)
            if chunk2 and chunk2.is_active:
                print("FAIL: chunk should be inactive after archive")
                return 1

            # 恢复 active 状态，避免污染测试库
            chunk2.is_active = True
            await db.commit()
            print("  apply_action archive/deactivate OK (restored active)")

    # 验证治理建议 REST API
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            f"/api/knowledge-bases/{kb.id}/governance/suggestions",
            params={"scan_duplicates": False},
        )
        if res.status_code != 200:
            print(f"FAIL: governance API {res.status_code}")
            return 1

    print("PASS: Phase 1.3 — 治理扫描与动作 API 正常")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
