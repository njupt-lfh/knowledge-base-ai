"""Gap 入库与 kb_id 前缀兼容

验证内容：
  - KbIdResolver 前缀解析与 Gap 入库 kb_id 兼容

运行方式（在 backend 目录）:
  pytest tests/test_kb_id_gap.py -v

预期结果：全部用例通过。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.gap_service import GapService
from app.utils.kb_id import KbIdResolver


@pytest.mark.asyncio
async def test_kb_resolver_prefix_to_full():
    """验证 kb_id 前缀解析。"""
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
    """验证 Gap 入库立即返回 processing 状态（后台异步执行）。"""
    import asyncio

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

    svc.db.commit = AsyncMock()
    svc.db.refresh = AsyncMock()

    with patch("app.services.gap_service.asyncio.create_task") as mock_create_task:
        result = await svc.ingest_gap(
            full, "gap-1", manual_content="人工补全正文，用于测试入库路径。"
        )

    # 验证同步阶段：状态已设为 processing
    assert gap.status == "processing"
    assert gap.kb_id == full
    assert result["gap_id"] == "gap-1"
    assert result["status"] == "processing"

    # 验证后台任务已创建
    mock_create_task.assert_called_once()

    # 验证后台任务参数（从 coro 中提取）
    call_args = mock_create_task.call_args[0]
    assert len(call_args) == 1
    coro = call_args[0]
    assert asyncio.iscoroutine(coro)
