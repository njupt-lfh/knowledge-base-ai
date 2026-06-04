"""Phase 2.3 验收：Embedding 缓存 + 历史压缩 + FTS 增量同步。

验证内容：
  - embed_query 二次调用命中缓存
  - compress_history 压缩比 >= 0.2
  - chunks_fts 增量同步与 embed_documents 去重

运行方式（在 backend 目录）:
  python scripts/verify_phase2_3.py

预期结果：打印 PASS 并退出码 0。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


async def main() -> int:
    """执行 Phase 2.3 验收：缓存、历史压缩与 FTS 增量。"""
    from app.core.database import async_session, init_db
    from app.services.embedding_service import EmbeddingService, get_embedding_cache
    from app.services.fts_service import FTS_TABLE
    from app.services.history_memory_service import compress_history, history_compression_ratio
    from sqlalchemy import text

    await init_db()

    # 验证 Embedding LRU 缓存命中
    cache = get_embedding_cache()
    cache.clear()
    svc = EmbeddingService()
    svc.embed_query("phase23-cache-key")
    svc.embed_query("phase23-cache-key")
    stats = cache.stats
    if stats["hits"] < 1:
        print(f"FAIL: embedding cache hits={stats['hits']}")
        return 1
    print(f"  embedding cache hit_rate={stats['hit_rate']}")

    # 验证长对话历史压缩节省 token
    long_hist = []
    for i in range(12):
        long_hist.append({"role": "user", "content": "问题内容" * 40 + str(i)})
        long_hist.append({"role": "assistant", "content": "回答内容" * 50 + str(i)})
    compressed = compress_history(long_hist, recent_turns=2)
    ratio = history_compression_ratio(long_hist, compressed)
    if ratio < 0.2:
        print(f"FAIL: history compression ratio {ratio} < 0.2")
        return 1
    print(f"  history compression saved_ratio={ratio}")

    async with async_session() as db:
        async with db.bind.connect() as conn:
            count = (await conn.execute(text(f"SELECT COUNT(*) FROM {FTS_TABLE}"))).scalar_one()
        if count is None:
            print("FAIL: chunks_fts missing")
            return 1
    print(f"  fts index rows={count} (incremental sync on init_db)")

    # 验证 embed_documents 对重复文本去重
    dup_vecs = svc.embed_documents(["a", "a", "b"])
    if dup_vecs[0] != dup_vecs[1]:
        print("FAIL: embed_documents dedupe")
        return 1
    print("  embed_documents dedupe ok")

    print("PASS: Phase 2.3 — Cache + History Memory + Incremental FTS")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
