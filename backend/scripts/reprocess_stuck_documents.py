"""重新处理卡在 processing 状态的文档。

验证内容：
  - 调用 recover_stuck_documents 扫描并重试超时文档

运行方式（在 backend 目录）:
  python scripts/reprocess_stuck_documents.py

预期结果：打印 attempted recover 数量并退出码 0。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


async def main() -> int:
    """初始化数据库并尝试恢复所有卡在 processing 的文档。"""
    from app.core.database import init_db
    from app.services.document_service import recover_stuck_documents

    await init_db()
    n = await recover_stuck_documents()
    print(f"done: attempted recover for {n} document(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
