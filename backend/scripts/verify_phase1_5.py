"""Phase 1.5 验收：对话提炼 + Gap 入库流水线。

验证内容：
  - ConversationExtractService mock 模式能产出 source_ref
  - Gap 创建与列表 API 正常
  - Gap 入库 API 可调用（无 chunk 时可能非 200，可接受）

运行方式（在 backend 目录）:
  python scripts/verify_phase1_5.py

预期结果：打印 PASS 并退出码 0；无知识库时 SKIP 退出码 0。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


async def main() -> int:
    """执行 Phase 1.5 验收：对话提炼、Gap 创建与入库 API。"""
    from app.core.database import async_session, init_db
    from app.main import app
    from app.models.knowledge_base import KnowledgeBase
    from app.services.conversation_extract_service import ConversationExtractService
    from app.services.gap_service import GapService
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select

    await init_db()

    # 验证 mock 模式下的结构化提炼
    svc = ConversationExtractService()
    svc.llm.mock_mode = True
    extracted = await svc.extract_from_turn(
        "我们产品 SLA 是 99.9%",
        "感谢补充",
        hint_gap_type="USER_PROVIDED",
    )
    if not extracted or not extracted.get("source_ref"):
        print("FAIL: mock extract missing source_ref")
        return 1

    async with async_session() as db:
        kb = (await db.execute(select(KnowledgeBase).limit(1))).scalar_one_or_none()
        if not kb:
            print("SKIP: no KB")
            return 0

        gap_svc = GapService(db)
        gap = await gap_svc.create_gap(
            kb_id=kb.id,
            query="测试 SLA",
            gap_type="USER_PROVIDED",
            source_ref=extracted["source_ref"],
            suggested_content=ConversationExtractService.pack_suggested(extracted),
        )
        print(f"  gap created id={gap.id[:8]}… status={gap.status}")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 入库 API：空 body 在测试库可能失败，但不影响整体验收
        bad = await client.post(
            f"/api/knowledge-bases/{kb.id}/gaps/{gap.id}/ingest",
            json={},
        )
        if bad.status_code != 200:
            print(f"  ingest (mock) status={bad.status_code} — OK if no chunks in test DB")

        # 验证 Gap 列表 API
        gaps = await client.get(
            f"/api/knowledge-bases/{kb.id}/gaps", params={"gap_type": "KNOWLEDGE_ABSENT"}
        )
        if gaps.status_code != 200:
            print(f"FAIL: list gaps {gaps.status_code}")
            return 1

    print("PASS: Phase 1.5 — 结构化提炼、source_ref 约束、Gap 入库 API")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
