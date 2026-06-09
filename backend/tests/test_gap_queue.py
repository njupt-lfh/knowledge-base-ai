"""Gap 队列视图与入库追溯字段测试。"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from app.core.database import async_session, init_db
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_gap import KnowledgeGap
from app.services.gap_service import GapService


@pytest.fixture
async def kb_id():
    await init_db()
    kid = f"kb-gap-queue-{uuid.uuid4().hex[:8]}"
    async with async_session() as db:
        db.add(KnowledgeBase(id=kid, name="gap-queue-test"))
        await db.commit()
    yield kid


@pytest.mark.asyncio
async def test_list_gaps_queue_pending_excludes_completed(kb_id):
    async with async_session() as db:
        pending = KnowledgeGap(
            kb_id=kb_id,
            query="待办问题",
            gap_type="RETRIEVAL_MISS",
            status="pending",
        )
        done = KnowledgeGap(
            kb_id=kb_id,
            query="已完成问题",
            gap_type="USER_CORRECTION",
            status="approved",
            document_id="doc-1",
        )
        db.add_all([pending, done])
        await db.commit()

        svc = GapService(db)
        pending_rows = await svc.list_gaps(kb_id, queue="pending")
        completed_rows = await svc.list_gaps(kb_id, queue="completed")

    assert {g.query for g in pending_rows} == {"待办问题"}
    assert {g.query for g in completed_rows} == {"已完成问题"}


@pytest.mark.asyncio
async def test_list_gaps_default_queue_is_pending(kb_id):
    async with async_session() as db:
        pending = KnowledgeGap(
            kb_id=kb_id,
            query="默认队列待办",
            gap_type="RETRIEVAL_MISS",
            status="pending",
        )
        done = KnowledgeGap(
            kb_id=kb_id,
            query="默认队列已完成",
            gap_type="USER_CORRECTION",
            status="approved",
        )
        db.add_all([pending, done])
        await db.commit()

        svc = GapService(db)
        default_rows = await svc.list_gaps(kb_id)
        all_rows = await svc.list_gaps(kb_id, queue="all")

    assert {g.query for g in default_rows} == {"默认队列待办"}
    assert {g.query for g in all_rows} == {"默认队列待办", "默认队列已完成"}


@pytest.mark.asyncio
async def test_update_status_sets_resolved_at(kb_id):
    async with async_session() as db:
        gap = KnowledgeGap(
            kb_id=kb_id,
            query="拒绝测试",
            gap_type="RETRIEVAL_MISS",
            status="pending",
        )
        db.add(gap)
        await db.commit()
        await db.refresh(gap)

        svc = GapService(db)
        updated = await svc.update_status(gap.id, "rejected")

    assert updated is not None
    assert updated.status == "rejected"
    assert updated.resolved_at is not None
    assert updated.updated_at is not None


@pytest.mark.asyncio
async def test_process_gap_ingest_sets_document_id(kb_id):
    from app.services import gap_service as gap_module

    gap_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())

    async with async_session() as db:
        gap = KnowledgeGap(
            id=gap_id,
            kb_id=kb_id,
            query="入库追溯",
            gap_type="USER_CORRECTION",
            status="processing",
            source_ref="正文",
        )
        db.add(gap)
        await db.commit()

    mock_doc = AsyncMock()
    mock_doc.id = doc_id
    mock_stats = AsyncMock()
    mock_stats.allowed = 1

    with patch.object(gap_module, "DocumentService") as doc_cls:
        doc_cls.return_value.ingest_manual_immediate = AsyncMock(
            return_value=(mock_doc, mock_stats)
        )
        await gap_module._process_gap_ingest(
            gap_id,
            kb_id,
            title="[Gap] 入库追溯",
            content="标准普尔四账户说明",
        )

    async with async_session() as db:
        gap = await db.get(KnowledgeGap, gap_id)

    assert gap is not None
    assert gap.status == "approved"
    assert gap.document_id == doc_id
    assert gap.resolved_at is not None
