"""Phase 1.4 验收：入库门禁 + knowledge_conflicts 表 + API。

验证内容：
  - knowledge_conflicts 表存在
  - distance_to_similarity 重复阈值计算正确
  - 预检与冲突列表 API 可正常响应

运行方式（在 backend 目录）:
  python scripts/verify_phase1_4.py

预期结果：打印 PASS 并退出码 0；无知识库时 SKIP 退出码 0。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


async def main() -> int:
    """执行 Phase 1.4 验收：入库门禁服务与冲突 API。"""
    from app.core.database import async_session, init_db, verify_schema
    from app.main import app
    from app.models.knowledge_base import KnowledgeBase
    from app.services.ingestion_gate_service import IngestionGateService, distance_to_similarity
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select

    await init_db()
    missing = await verify_schema()
    if "knowledge_conflicts" in missing:
        print(f"FAIL: knowledge_conflicts missing: {missing}")
        return 1

    # 验证距离→相似度换算满足重复判定阈值
    sim = distance_to_similarity(0.4)
    if sim < 0.91:
        print(f"FAIL: duplicate threshold sim={sim}")
        return 1

    async with async_session() as db:
        kb = (await db.execute(select(KnowledgeBase).limit(1))).scalar_one_or_none()
        if not kb:
            print("SKIP: no KB")
            return 0

        gate = IngestionGateService(db)
        result = await gate.check_content(kb.id, "unique verification content xyz-1.4")
        if result.status not in ("allow", "duplicate", "conflict"):
            print(f"FAIL: unexpected status {result.status}")
            return 1
        print(f"  precheck status={result.status} llm_calls={result.llm_calls}")

    # 验证预检与冲突列表 REST API
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        pre = await client.post(
            f"/api/knowledge-bases/{kb.id}/ingestion/precheck",
            json={"content": "precheck sample 1.4"},
        )
        if pre.status_code != 200:
            print(f"FAIL: precheck API {pre.status_code}")
            return 1

        conf = await client.get(f"/api/knowledge-bases/{kb.id}/conflicts")
        if conf.status_code != 200:
            print(f"FAIL: conflicts API {conf.status_code}")
            return 1

    print("PASS: Phase 1.4 — 入库门禁表、预检与冲突 API 正常")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
