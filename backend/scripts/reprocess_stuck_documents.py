#!/usr/bin/env python3
"""重新处理卡在 processing 状态的文档。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


async def main() -> int:
    from app.core.database import init_db
    from app.services.document_service import recover_stuck_documents

    await init_db()
    n = await recover_stuck_documents()
    print(f"done: attempted recover for {n} document(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
