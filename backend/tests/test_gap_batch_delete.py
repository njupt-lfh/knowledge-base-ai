"""Gap 批量删除测试。"""

import uuid

import pytest
from app.core.database import async_session, init_db
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_gap import KnowledgeGap
from app.services.gap_service import GapService


@pytest.fixture
async def kb_id():
    await init_db()
    kid = f"kb-gap-batch-del-{uuid.uuid4().hex[:8]}"
    async with async_session() as db:
        db.add(KnowledgeBase(id=kid, name="gap-batch-del"))
        await db.commit()
    yield kid


@pytest.mark.asyncio
async def test_delete_gaps_batch_skips_processing(kb_id):
    async with async_session() as db:
        deletable = KnowledgeGap(
            kb_id=kb_id,
            query="可删",
            gap_type="RETRIEVAL_MISS",
            status="pending",
        )
        processing = KnowledgeGap(
            kb_id=kb_id,
            query="入库中",
            gap_type="USER_CORRECTION",
            status="processing",
        )
        db.add_all([deletable, processing])
        await db.commit()
        await db.refresh(deletable)
        await db.refresh(processing)

        svc = GapService(db)
        result = await svc.delete_gaps_batch(kb_id, [deletable.id, processing.id])

    assert result["deleted"] == 1
    assert result["skipped"] == 1


@pytest.mark.asyncio
async def test_delete_gap_rejects_processing(kb_id):
    async with async_session() as db:
        gap = KnowledgeGap(
            kb_id=kb_id,
            query="禁止删",
            gap_type="USER_CORRECTION",
            status="processing",
        )
        db.add(gap)
        await db.commit()
        await db.refresh(gap)

        svc = GapService(db)
        with pytest.raises(ValueError, match="processing"):
            await svc.delete_gap(gap.id)
