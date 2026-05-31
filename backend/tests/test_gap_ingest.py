from unittest.mock import AsyncMock, MagicMock

import pytest
from app.services.gap_service import GapService


@pytest.mark.asyncio
async def test_ingest_knowledge_absent_requires_manual():
    svc = GapService(db=MagicMock())
    gap = MagicMock()
    gap.kb_id = "kb1"
    gap.gap_type = "KNOWLEDGE_ABSENT"
    gap.source_ref = None
    gap.suggested_content = None
    svc.db.get = AsyncMock(return_value=gap)
    svc._canonical_kb_id = AsyncMock(return_value="kb1")
    with pytest.raises(ValueError, match="人工"):
        await svc.ingest_gap("kb1", "g1")


@pytest.mark.asyncio
async def test_ingest_user_provided_requires_source_ref():
    svc = GapService(db=MagicMock())
    gap = MagicMock()
    gap.kb_id = "kb1"
    gap.gap_type = "USER_PROVIDED"
    gap.source_ref = None
    gap.suggested_content = '{"content":"x"}'
    svc.db.get = AsyncMock(return_value=gap)
    svc._canonical_kb_id = AsyncMock(return_value="kb1")
    with pytest.raises(ValueError, match="source_ref"):
        await svc.ingest_gap("kb1", "g1")
