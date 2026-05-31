import pytest
from app.services.fts_service import build_fts_query, search_fts, upsert_chunk_fts


def test_build_fts_query_chinese():
    q = build_fts_query("什么是 RAG 检索增强")
    assert q is not None
    assert "RAG" in q or "检索" in q


@pytest.mark.asyncio
async def test_fts_roundtrip():
    import uuid

    from app.core.database import async_session, init_db
    from app.models.chunk import Chunk
    from app.models.document import Document
    from app.models.knowledge_base import KnowledgeBase

    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb-fts-{suffix}"
    doc_id = f"d-fts-{suffix}"
    chunk_id = f"c-fts-{suffix}"

    async with async_session() as db:
        kb = KnowledgeBase(
            id=kb_id,
            name="fts-test",
            embedding_model="m",
            chunk_size=500,
            chunk_overlap=50,
        )
        db.add(kb)
        doc = Document(
            id=doc_id,
            knowledge_base_id=kb_id,
            filename="t.txt",
            file_type="txt",
            status="completed",
        )
        db.add(doc)
        chunk = Chunk(
            id=chunk_id,
            document_id=doc_id,
            knowledge_base_id=kb_id,
            content="dotenv 用于加载环境变量配置",
            chunk_index=0,
            char_count=20,
            is_active=True,
        )
        db.add(chunk)
        await db.commit()

        await upsert_chunk_fts(db, chunk_id, kb_id, chunk.content)
        await db.commit()

        hits = await search_fts(db, kb_id, "dotenv 环境变量", limit=5)
        assert any(h[0] == chunk_id for h in hits)
