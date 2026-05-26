"""Gap / Feedback API 在完整 schema 下可正常响应（非 500）"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import async_session, init_db
from app.main import app
from app.models.knowledge_base import KnowledgeBase


@pytest.mark.asyncio
async def test_gap_and_feedback_routes_not_500():
    await init_db()

    async with async_session() as db:
        kb = (await db.execute(select(KnowledgeBase).limit(1))).scalar_one_or_none()
    if not kb:
        pytest.skip("no knowledge base in DB")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        gap_res = await client.get(f"/api/knowledge-bases/{kb.id}/gaps")
        assert gap_res.status_code == 200, gap_res.text

        fb_res = await client.post(
            f"/api/knowledge-bases/{kb.id}/feedback",
            json={
                "message_id": "00000000-0000-0000-0000-000000000099",
                "feedback_type": "like",
            },
        )
        assert fb_res.status_code in (400, 404), fb_res.text  # message 不存在，但不应 500
