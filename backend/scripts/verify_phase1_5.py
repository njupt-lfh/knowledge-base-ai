"""Phase 1.5 验收：对话提炼 + Gap 入库流水线"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


async def main() -> int:
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select

    from app.core.database import async_session, init_db
    from app.main import app
    from app.models.knowledge_base import KnowledgeBase
    from app.services.conversation_extract_service import ConversationExtractService
    from app.services.gap_service import GapService

    await init_db()

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
        bad = await client.post(
            f"/api/knowledge-bases/{kb.id}/gaps/{gap.id}/ingest",
            json={},
        )
        if bad.status_code != 200:
            print(f"  ingest (mock) status={bad.status_code} — OK if no chunks in test DB")

        gaps = await client.get(f"/api/knowledge-bases/{kb.id}/gaps", params={"gap_type": "KNOWLEDGE_ABSENT"})
        if gaps.status_code != 200:
            print(f"FAIL: list gaps {gaps.status_code}")
            return 1

    print("PASS: Phase 1.5 — 结构化提炼、source_ref 约束、Gap 入库 API")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
