"""ConflictService 单元测试：冲突列表应返回知识块来源信息。"""

import uuid
from unittest.mock import patch

import pytest
from app.core.database import async_session, init_db
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_conflict import KnowledgeConflict
from app.services.conflict_service import ConflictService


@pytest.fixture
async def kb_with_conflict():
    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb-conflict-{suffix}"
    doc_id = f"doc-conflict-{suffix}"
    chunk_id = f"chunk-conflict-{suffix}"
    conflict_id = f"conflict-{suffix}"
    source_doc_id = f"doc-new-{suffix}"

    async with async_session() as db:
        db.add(KnowledgeBase(id=kb_id, name=f"conflict-kb-{suffix}"))
        db.add(
            Document(
                id=doc_id,
                knowledge_base_id=kb_id,
                filename="existing.md",
                file_type="markdown",
                file_path=f"/tmp/{doc_id}.md",
            )
        )
        db.add(
            Document(
                id=source_doc_id,
                knowledge_base_id=kb_id,
                filename="incoming.md",
                file_type="markdown",
                file_path=f"/tmp/{source_doc_id}.md",
            )
        )
        db.add(
            Chunk(
                id=chunk_id,
                document_id=doc_id,
                knowledge_base_id=kb_id,
                content="已有知识块内容",
                chunk_index=3,
                char_count=8,
            )
        )
        db.add(
            KnowledgeConflict(
                id=conflict_id,
                knowledge_base_id=kb_id,
                existing_chunk_id=chunk_id,
                new_content="待入库的新内容",
                similarity=0.88,
                status="pending",
                llm_reason="语义冲突",
                source_document_id=source_doc_id,
            )
        )
        await db.commit()

    yield {
        "kb_id": kb_id,
        "conflict_id": conflict_id,
        "chunk_id": chunk_id,
        "doc_id": doc_id,
        "source_doc_id": source_doc_id,
    }

    async with async_session() as db:
        row = await db.get(KnowledgeConflict, conflict_id)
        if row:
            await db.delete(row)
        chunk = await db.get(Chunk, chunk_id)
        if chunk:
            await db.delete(chunk)
        for did in (doc_id, source_doc_id):
            doc = await db.get(Document, did)
            if doc:
                await db.delete(doc)
        kb = await db.get(KnowledgeBase, kb_id)
        if kb:
            await db.delete(kb)
        await db.commit()


@pytest.mark.asyncio
async def test_list_pending_includes_chunk_refs(kb_with_conflict):
    """冲突列表应附带 existing_chunk_ref 与 source_document_name。"""
    data = kb_with_conflict
    async with async_session() as db:
        svc = ConflictService(db)
        rows = await svc.list_pending(data["kb_id"])

    assert len(rows) == 1
    row = rows[0]
    assert row["existing_chunk_ref"]["document_name"] == "existing.md"
    assert row["existing_chunk_ref"]["chunk_index"] == 3
    assert row["existing_chunk_ref"]["chunk_id"] == data["chunk_id"]
    assert row["source_document_name"] == "incoming.md"
    assert "已有知识块" in row["existing_preview"]


@pytest.mark.asyncio
async def test_list_history_excludes_pending(kb_with_conflict):
    """history 状态应只返回已裁决记录。"""
    data = kb_with_conflict
    async with async_session() as db:
        row = await db.get(KnowledgeConflict, data["conflict_id"])
        row.status = "resolved_keep_old"
        row.resolved_at = row.created_at
        await db.commit()

    async with async_session() as db:
        svc = ConflictService(db)
        pending = await svc.list_conflicts(data["kb_id"], status="pending")
        history = await svc.list_conflicts(data["kb_id"], status="history")

    assert pending == []
    assert len(history) == 1
    assert history[0]["status"] == "resolved_keep_old"
    assert history[0]["resolved_at"] is not None


@pytest.mark.asyncio
async def test_rollback_restores_pending(kb_with_conflict):
    """回退已裁决冲突应恢复为 pending。"""
    data = kb_with_conflict
    async with async_session() as db:
        row = await db.get(KnowledgeConflict, data["conflict_id"])
        row.status = "dismissed"
        row.resolved_at = row.created_at
        await db.commit()

    async with async_session() as db:
        svc = ConflictService(db)
        result = await svc.rollback(data["kb_id"], data["conflict_id"])

    assert result["status"] == "pending"
    assert result["prev_status"] == "dismissed"
    assert result["resolved_at"] is None

    async with async_session() as db:
        svc = ConflictService(db)
        pending = await svc.list_conflicts(data["kb_id"], status="pending")
    assert len(pending) == 1


@pytest.mark.asyncio
async def test_rollback_keep_new_removes_created_chunk(kb_with_conflict):
    """回退「保留新内容」应删除误写入的 chunk。"""
    data = kb_with_conflict
    new_chunk_id = f"chunk-new-{uuid.uuid4().hex[:8]}"
    async with async_session() as db:
        db.add(
            Chunk(
                id=new_chunk_id,
                document_id=data["doc_id"],
                knowledge_base_id=data["kb_id"],
                content="误入库内容",
                chunk_index=99,
                char_count=5,
            )
        )
        row = await db.get(KnowledgeConflict, data["conflict_id"])
        row.status = "resolved_keep_new"
        row.resolved_chunk_id = new_chunk_id
        row.resolved_at = row.created_at
        await db.commit()

    async with async_session() as db:
        svc = ConflictService(db)
        mock_collection = type("C", (), {"delete": lambda self, ids: None})()
        with patch("app.services.conflict_service.get_collection", return_value=mock_collection):
            result = await svc.rollback(data["kb_id"], data["conflict_id"])

    assert result["status"] == "pending"
    assert result["prev_status"] == "resolved_keep_new"
    async with async_session() as db:
        assert await db.get(Chunk, new_chunk_id) is None
