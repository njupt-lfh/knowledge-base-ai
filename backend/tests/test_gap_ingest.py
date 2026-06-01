"""Gap 入库约束单元测试。

验证内容：
  - KNOWLEDGE_ABSENT 无人工内容时拒绝入库
  - USER_PROVIDED 无 source_ref 时拒绝入库

运行方式（在 backend 目录）:
  pytest tests/test_gap_ingest.py -v

预期结果：全部用例通过。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.services.gap_service import GapService


@pytest.mark.asyncio
async def test_ingest_knowledge_absent_requires_manual():
    """知识缺失类 Gap 无 manual_content 应抛出 ValueError。"""
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
    """用户补充类 Gap 无 source_ref 应抛出 ValueError。"""
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
