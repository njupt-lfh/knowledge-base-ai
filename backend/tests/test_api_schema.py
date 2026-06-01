"""Gap / Feedback API 在完整 schema 下可正常响应（非 500）

验证内容：
  - Gap/Feedback API 在完整 schema 下非 500

运行方式（在 backend 目录）:
  pytest tests/test_api_schema.py -v

预期结果：全部用例通过。
"""

import pytest
from app.core.database import async_session, init_db
from app.main import app
from app.models.knowledge_base import KnowledgeBase
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select


@pytest.mark.asyncio
async def test_gap_and_feedback_routes_not_500():
    """验证 Gap/Feedback 路由非 500。"""
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
