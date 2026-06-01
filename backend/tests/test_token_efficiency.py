"""Phase 2.3 单元测试 — Embedding 缓存 + 历史压缩 + FTS 增量

验证内容：
  - Embedding 缓存、历史压缩、FTS 增量同步

运行方式（在 backend 目录）:
  pytest tests/test_token_efficiency.py -v

预期结果：全部用例通过。
"""

import uuid

import pytest
from app.services.embedding_cache import EmbeddingCache
from app.services.embedding_service import EmbeddingService, get_embedding_cache
from app.services.history_memory_service import (
    compress_history,
    estimate_messages_chars,
    history_compression_ratio,
)


def test_embedding_cache_hit():
    """验证 Embedding 缓存命中。"""
    cache = EmbeddingCache(maxsize=10)
    cache.set("hello", [1.0, 2.0])
    assert cache.get("hello") == [1.0, 2.0]
    assert cache.hits == 1
    assert cache.get("missing") is None
    assert cache.misses == 1


def test_embed_query_uses_cache():
    """验证 Embedding 缓存命中。"""
    cache = get_embedding_cache()
    cache.clear()
    svc = EmbeddingService()
    a = svc.embed_query("repeat-me")
    b = svc.embed_query("repeat-me")
    assert a == b
    assert cache.hits >= 1


def test_embed_documents_dedupes():
    """验证重复图片去重。"""
    cache = get_embedding_cache()
    cache.clear()
    svc = EmbeddingService()
    vecs = svc.embed_documents(["same", "same", "other"])
    assert len(vecs) == 3
    assert vecs[0] == vecs[1]
    assert cache.misses == 2


def test_compress_history_keeps_recent():
    """验证上下文压缩预算。"""
    long_hist = []
    for i in range(8):
        long_hist.append({"role": "user", "content": "问题" * 30 + str(i)})
        long_hist.append({"role": "assistant", "content": "回答" * 40 + str(i)})

    compressed = compress_history(long_hist, recent_turns=2)
    assert len(compressed) <= 5
    assert compressed[-1]["role"] == "assistant"
    assert compressed[-2]["role"] == "user"
    assert compressed[0]["role"] == "system"
    assert "此前对话摘要" in compressed[0]["content"]


def test_history_compression_saves_tokens():
    """验证上下文压缩预算。"""
    long_hist = []
    for _i in range(12):
        long_hist.append({"role": "user", "content": "X" * 200})
        long_hist.append({"role": "assistant", "content": "Y" * 250})

    compressed = compress_history(long_hist, recent_turns=2)
    ratio = history_compression_ratio(long_hist, compressed)
    assert estimate_messages_chars(compressed) < estimate_messages_chars(long_hist)
    assert ratio >= 0.2


@pytest.mark.asyncio
async def test_fts_incremental_sync():
    """验证 FTS 增量同步。"""
    from app.core.database import async_session, init_db
    from app.models.chunk import Chunk
    from app.models.document import Document
    from app.models.knowledge_base import KnowledgeBase
    from app.services.fts_service import FTS_TABLE, ensure_fts_schema, sync_fts_incremental
    from sqlalchemy import text

    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb-inc-{suffix}"
    doc_id = f"d-inc-{suffix}"
    chunk_id = f"c-inc-{suffix}"

    async with async_session() as db:
        async with db.bind.connect() as conn:
            await ensure_fts_schema(conn)
            before = (await conn.execute(text(f"SELECT COUNT(*) FROM {FTS_TABLE}"))).scalar_one()

        kb = KnowledgeBase(
            id=kb_id,
            name="inc",
            embedding_model="m",
            chunk_size=500,
            chunk_overlap=50,
        )
        doc = Document(
            id=doc_id,
            knowledge_base_id=kb_id,
            filename="t.txt",
            file_type="txt",
            status="completed",
        )
        chunk = Chunk(
            id=chunk_id,
            document_id=doc_id,
            knowledge_base_id=kb_id,
            content="incremental fts token efficiency",
            chunk_index=0,
            char_count=30,
            is_active=True,
        )
        db.add(kb)
        db.add(doc)
        db.add(chunk)
        await db.commit()

        async with db.bind.connect() as conn:
            synced = await sync_fts_incremental(conn)
            await conn.commit()
            after = (await conn.execute(text(f"SELECT COUNT(*) FROM {FTS_TABLE}"))).scalar_one()

        assert synced >= 1
        assert after >= before + 1
