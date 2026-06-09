"""Gap 处理记录（audit log）测试。"""

import uuid

import pytest
from app.core.database import async_session, init_db
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_gap import KnowledgeGap
from app.services.gap_service import GapService


@pytest.fixture
async def kb_id():
    await init_db()
    kid = f"kb-gap-audit-{uuid.uuid4().hex[:8]}"
    async with async_session() as db:
        db.add(KnowledgeBase(id=kid, name="gap-audit-test"))
        await db.commit()
    yield kid


@pytest.mark.asyncio
async def test_create_gap_writes_audit_log(kb_id):
    async with async_session() as db:
        svc = GapService(db)
        gap = await svc.create_gap(
            kb_id=kb_id,
            query="审计测试",
            gap_type="RETRIEVAL_MISS",
        )
        logs = await svc.get_audit_log(kb_id, gap.id)

    assert len(logs) >= 1
    assert logs[0].action == "created"
    assert "RETRIEVAL_MISS" in (logs[0].detail or "")


@pytest.mark.asyncio
async def test_update_status_writes_audit_log(kb_id):
    async with async_session() as db:
        gap = KnowledgeGap(
            kb_id=kb_id,
            query="状态变更",
            gap_type="RETRIEVAL_MISS",
            status="pending",
        )
        db.add(gap)
        await db.commit()
        await db.refresh(gap)

        svc = GapService(db)
        await svc.update_status(gap.id, "rejected")
        logs = await svc.get_audit_log(kb_id, gap.id)

    assert any(log.action == "status_changed" for log in logs)
    assert any("pending -> rejected" in (log.detail or "") for log in logs)


@pytest.mark.asyncio
async def test_delete_gap_writes_audit_log(kb_id):
    async with async_session() as db:
        gap = KnowledgeGap(
            kb_id=kb_id,
            query="删除记录",
            gap_type="RETRIEVAL_MISS",
            status="pending",
        )
        db.add(gap)
        await db.commit()
        await db.refresh(gap)
        gap_id = gap.id

        svc = GapService(db)
        ok = await svc.delete_gap(gap_id)

    assert ok is True
    async with async_session() as db:
        svc = GapService(db)
        logs = await svc.get_audit_log(kb_id, gap_id)

    assert any(log.action == "deleted" for log in logs)
