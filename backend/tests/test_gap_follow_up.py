"""Gap 续补（follow-up）测试。"""

import uuid

import pytest
from app.core.database import async_session, init_db
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_gap import KnowledgeGap
from app.services.gap_service import GapService


@pytest.fixture
async def kb_id():
    await init_db()
    kid = f"kb-gap-follow-{uuid.uuid4().hex[:8]}"
    async with async_session() as db:
        db.add(KnowledgeBase(id=kid, name="gap-follow-test"))
        await db.commit()
    yield kid


@pytest.mark.asyncio
async def test_create_follow_up_links_parent_and_pending_queue(kb_id):
    async with async_session() as db:
        parent = KnowledgeGap(
            kb_id=kb_id,
            query="标准普尔四账户",
            gap_type="USER_CORRECTION",
            status="approved",
            document_id="doc-parent",
        )
        db.add(parent)
        await db.commit()
        await db.refresh(parent)

        svc = GapService(db)
        child = await svc.create_follow_up(
            kb_id,
            parent.id,
            correction_text="补充：第四个账户是消费账户",
        )
        pending = await svc.list_gaps(kb_id, queue="pending")
        parent_logs = await svc.get_audit_log(kb_id, parent.id)

    assert child.parent_gap_id == parent.id
    assert child.gap_type == "USER_CORRECTION"
    assert child.status == "suggested"
    assert any(g.id == child.id for g in pending)
    assert any(log.action == "follow_up_created" for log in parent_logs)


@pytest.mark.asyncio
async def test_create_follow_up_rejects_non_approved(kb_id):
    async with async_session() as db:
        parent = KnowledgeGap(
            kb_id=kb_id,
            query="未入库",
            gap_type="RETRIEVAL_MISS",
            status="pending",
        )
        db.add(parent)
        await db.commit()
        await db.refresh(parent)

        svc = GapService(db)
        with pytest.raises(ValueError, match="仅已入库"):
            await svc.create_follow_up(kb_id, parent.id, correction_text="补充内容")
