"""Phase 1.1 验收：Gap 队列 + 反馈触发 + DB 表。

验证内容：
  - knowledge_gaps 等 ORM 表已创建
  - GapService 能识别中文拒答话术并触发入队

运行方式（在 backend 目录）:
  python scripts/verify_phase1_1.py

预期结果：打印 PASS 并退出码 0；表缺失或入队逻辑异常时退出码 1。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 将 backend 根目录加入 sys.path，以便直接运行脚本
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


async def main() -> int:
    """执行 Phase 1.1 验收：校验 schema 与 Gap 中文拒答检测逻辑。"""
    from app.core.database import init_db, verify_schema
    from app.services.gap_service import GapService

    await init_db()
    missing = await verify_schema()
    if missing:
        print(f"FAIL: missing tables {missing}")
        return 1

    if "knowledge_gaps" in missing or await verify_schema():
        pass

    # 验证：空来源 + 中文拒答话术应触发入队
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
