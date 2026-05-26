"""Phase 1.2 验收：质量分计算 + DB 表 + API 路由"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


async def main() -> int:
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select

    from app.core.database import async_session, init_db, verify_schema
    from app.main import app
    from app.models.chunk import Chunk
    from app.models.knowledge_base import KnowledgeBase
    from app.services.quality_service import QualityService, compute_quality_score

    await init_db()
    missing = await verify_schema()
    if "chunk_quality" in missing:
        print(f"FAIL: chunk_quality table missing: {missing}")
        return 1

    score = compute_quality_score(
        hit_count=10, like_count=8, dislike_count=1, correction_count=0, created_at=None
    )
    if not (0 <= score <= 1):
        print(f"FAIL: invalid score {score}")
        return 1

    async with async_session() as db:
        kb = (await db.execute(select(KnowledgeBase).limit(1))).scalar_one_or_none()
        if kb:
            chunk = (
                await db.execute(select(Chunk).where(Chunk.knowledge_base_id == kb.id).limit(1))
            ).scalar_one_or_none()
            if chunk:
                svc = QualityService(db)
                q = await svc.recalculate_chunk(chunk.id)
                assert q is not None
                print(f"  sample chunk quality_score={q.quality_score}")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        if kb:
            res = await client.get(f"/api/knowledge-bases/{kb.id}/quality/low-quality")
            if res.status_code != 200:
                print(f"FAIL: low-quality API {res.status_code}")
                return 1

    print("PASS: Phase 1.2 — chunk_quality 表、质量分计算、API 正常")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
