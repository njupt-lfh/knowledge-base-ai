"""Gap 入库与 kb_id 前缀兼容"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.gap_service import GapService
from app.utils.kb_id import KbIdResolver


@pytest.mark.asyncio
async def test_kb_resolver_prefix_to_full():
    db = MagicMock()
    full = "e3752f00-b894-429e-a982-43142c5f0d8a"
    kb = MagicMock()
    kb.id = full
    db.get = AsyncMock(side_effect=lambda model, id_: kb if id_ == full else None)
    db.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[full])))
        )
    )
    resolver = KbIdResolver(db)
    assert await resolver.resolve("e3752f00") == full
    assert resolver.gap_kb_matches("e3752f00", full)


@pytest.mark.asyncio
async def test_ingest_gap_accepts_full_url_with_legacy_gap_kb():
    full = "e3752f00-b894-429e-a982-43142c5f0d8a"
    svc = GapService(db=MagicMock())
    gap = MagicMock()
    gap.id = "gap-1"
    gap.kb_id = "e3752f00"
    gap.gap_type = "KNOWLEDGE_ABSENT"
    gap.query = "test query"
    gap.source_ref = None
    gap.suggested_content = None
    svc.db.get = AsyncMock(return_value=gap)
    svc._canonical_kb_id = AsyncMock(return_value=full)
    svc._kb_resolver.gap_kb_matches = lambda g, c: g == "e3752f00" and c == full

    mock_doc = MagicMock()
    mock_doc.id = "doc-1"
    mock_stats = MagicMock(allowed=1, duplicates=0, conflicts=0)

    with patch("app.services.gap_service.DocumentService") as DocSvc:
        DocSvc.return_value.ingest_manual_immediate = AsyncMock(return_value=(mock_doc, mock_stats))
        svc.db.commit = AsyncMock()
        svc.db.refresh = AsyncMock()
        result = await svc.ingest_gap(
            full, "gap-1", manual_content="人工补全正文，用于测试入库路径。"
        )

    assert result["gap_id"] == "gap-1"
    assert gap.kb_id == full
    DocSvc.return_value.ingest_manual_immediate.assert_awaited_once_with(
        full, "[Gap] test query", "人工补全正文，用于测试入库路径。"
    )
