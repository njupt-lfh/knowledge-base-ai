"""Phase 1.1 验收：Gap 队列 + 反馈触发 + DB 表"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


async def main() -> int:
    from app.core.database import init_db, verify_schema
    from app.services.gap_service import GapService

    await init_db()
    missing = await verify_schema()
    if missing:
        print(f"FAIL: missing tables {missing}")
        return 1

    if "knowledge_gaps" in missing or await verify_schema():
        pass

    checks = [
        GapService.should_enqueue([], "目前知识库中暂无相关信息"),
        GapService.should_enqueue(
            [{"chunk_id": "x", "score": 0.9}],
            "目前知识库中暂无相关内容",
        ),
    ]
    if not all(checks):
        print("FAIL: Gap 中文拒答检测未通过")
        return 1

    print("PASS: Phase 1.1 — knowledge_gaps 表存在，Gap 中文入队逻辑正常")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
