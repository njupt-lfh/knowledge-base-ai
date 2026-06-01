"""文档入库 FTS 同步 — Phase 2 审计 bug 回归

验证内容：
  - 文档入库/手动录入/toggle 与 FTS5 同步

运行方式（在 backend 目录）:
  pytest tests/test_document_fts_sync.py -v

预期结果：全部用例通过。
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from app.services.document_service import (
    DocumentService,
    _process_document,
    _process_manual,
    _sync_chunks_to_fts,
)
from app.services.fts_service import FTS_TABLE, search_fts
from sqlalchemy import text


@pytest.mark.asyncio
async def test_sync_chunks_to_fts_helper():
    """测试：sync chunks to fts helper。"""
    from app.core.database import async_session, init_db
    from app.models.chunk import Chunk
    from app.models.document import Document
    from app.models.knowledge_base import KnowledgeBase

    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb-doc-fts-{suffix}"
    doc_id = f"d-doc-fts-{suffix}"
    chunk_id = f"c-doc-fts-{suffix}"

    async with async_session() as db:
        db.add(
            KnowledgeBase(
                id=kb_id,
                name="t",
                embedding_model="m",
                chunk_size=500,
                chunk_overlap=50,
            )
        )
        db.add(
            Document(
                id=doc_id,
                knowledge_base_id=kb_id,
                filename="t.txt",
                file_type="txt",
                status="completed",
            )
        )
        chunk = Chunk(
            id=chunk_id,
            document_id=doc_id,
            knowledge_base_id=kb_id,
            content="upload path must sync dotenv 环境变量",
            chunk_index=0,
            char_count=30,
            is_active=True,
        )
        db.add(chunk)
        await db.commit()

        await _sync_chunks_to_fts(db, kb_id, [chunk])
        hits = await search_fts(db, kb_id, "dotenv 环境变量", limit=5)
        assert any(h[0] == chunk_id for h in hits)


@pytest.mark.asyncio
async def test_process_manual_syncs_fts():
    """测试：process manual syncs fts。"""
    from app.core.database import async_session, init_db
    from app.models.document import Document
    from app.models.knowledge_base import KnowledgeBase

    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb-manual-{suffix}"
    doc_id = f"d-manual-{suffix}"
    content = "手动录入内容包含 uniquekeywordxyz 用于 FTS 检索验证。"

    async with async_session() as db:
        db.add(
            KnowledgeBase(
                id=kb_id,
                name="manual-kb",
                embedding_model="m",
                chunk_size=500,
                chunk_overlap=50,
            )
        )
        db.add(
            Document(
                id=doc_id,
                knowledge_base_id=kb_id,
                filename="manual",
                file_type="manual",
                status="processing",
            )
        )
        await db.commit()

    fake_collection = MagicMock()
    with patch("app.core.chroma_client.get_collection", return_value=fake_collection):
        with patch("app.services.document_service.get_collection", return_value=fake_collection):
            with patch(
                "app.services.embedding_service.EmbeddingService.embed_documents",
                return_value=[[0.1] * 256],
            ):
                await _process_manual(doc_id, kb_id, "manual", content)

    async with async_session() as db:
        hits = await search_fts(db, kb_id, "uniquekeywordxyz", limit=5)
        assert hits, "manual ingest should upsert chunks into FTS5"

        row = (
            await db.execute(
                text(f"SELECT COUNT(*) FROM {FTS_TABLE} WHERE knowledge_base_id = :kb"),
                {"kb": kb_id},
            )
        ).scalar_one()
        assert row >= 1


@pytest.mark.asyncio
async def test_process_document_syncs_fts():
    """验证文档/PDF 入库流程。"""
    from app.core.database import async_session, init_db
    from app.models.document import Document
    from app.models.knowledge_base import KnowledgeBase

    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb-upload-{suffix}"
    doc_id = f"d-upload-{suffix}"
    upload_kw = f"uploadkeyword{suffix}"

    async with async_session() as db:
        db.add(
            KnowledgeBase(
                id=kb_id,
                name="upload-kb",
                embedding_model="m",
                chunk_size=500,
                chunk_overlap=50,
            )
        )
        db.add(
            Document(
                id=doc_id,
                knowledge_base_id=kb_id,
                filename="sample.txt",
                file_type="txt",
                status="processing",
            )
        )
        await db.commit()

    fake_collection = MagicMock()
    with patch("app.services.document_service.resolve_upload_path", return_value="/tmp/sample.txt"):
        with patch("app.core.chroma_client.get_collection", return_value=fake_collection):
            with patch("app.services.document_service.get_collection", return_value=fake_collection):
                with patch(
                    "app.services.embedding_service.EmbeddingService.embed_documents",
                    return_value=[[0.1] * 256],
                ):
                    with patch(
                        "app.services.chunking_service.DocumentParser.parse",
                        return_value=f"上传文档内容 {upload_kw} 应同步到 FTS。",
                    ):
                        await _process_document(doc_id, kb_id, "txt", "/tmp/sample.txt")

    async with async_session() as db:
        hits = await search_fts(db, kb_id, upload_kw, limit=5)
        assert hits, "upload ingest should upsert chunks into FTS5"


@pytest.mark.asyncio
async def test_toggle_status_syncs_fts():
    """验证文档启停与 FTS 同步。"""
    from app.core.database import async_session, init_db
    from app.models.chunk import Chunk
    from app.models.document import Document
    from app.models.knowledge_base import KnowledgeBase

    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb-toggle-{suffix}"
    doc_id = f"d-toggle-{suffix}"
    chunk_id = f"c-toggle-{suffix}"
    kw = f"togglekeyword{suffix}"

    async with async_session() as db:
        db.add(
            KnowledgeBase(
                id=kb_id,
                name="toggle-kb",
                embedding_model="m",
                chunk_size=500,
                chunk_overlap=50,
            )
        )
        db.add(
            Document(
                id=doc_id,
                knowledge_base_id=kb_id,
                filename="t.txt",
                file_type="txt",
                status="completed",
                is_active=True,
            )
        )
        db.add(
            Chunk(
                id=chunk_id,
                document_id=doc_id,
                knowledge_base_id=kb_id,
                content=f"toggle test {kw}",
                chunk_index=0,
                char_count=20,
                is_active=True,
            )
        )
        await db.commit()
        await _sync_chunks_to_fts(db, kb_id, [(await db.get(Chunk, chunk_id))])

    fake_collection = MagicMock()
    with patch("app.services.document_service.get_collection", return_value=fake_collection):
        with patch(
            "app.services.embedding_service.EmbeddingService.embed_query",
            return_value=[0.1] * 256,
        ):
            async with async_session() as db:
                svc = DocumentService(db)
                await svc.toggle_status(doc_id, False)
                hits = await search_fts(db, kb_id, kw, limit=5)
                assert not hits

                await svc.toggle_status(doc_id, True)
                hits = await search_fts(db, kb_id, kw, limit=5)
                assert hits
