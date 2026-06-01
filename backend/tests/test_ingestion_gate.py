"""IngestionGateService 入库门禁单元测试。

验证内容：
  - 入库门禁 duplicate/conflict/allow 判定

运行方式（在 backend 目录）:
  pytest tests/test_ingestion_gate.py -v

预期结果：全部用例通过。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.ingestion_gate_service import (
    CONFLICT_MAX_DISTANCE,
    DUPLICATE_MAX_DISTANCE,
    IngestionGateService,
    distance_to_similarity,
)


def test_distance_to_similarity():
    """距离 0 对应相似度 1.0；DUPLICATE 阈值距离约 0.92 相似度。"""
    assert distance_to_similarity(0.0) == 1.0
    assert distance_to_similarity(DUPLICATE_MAX_DISTANCE) == pytest.approx(0.92, abs=0.01)


def test_threshold_ordering():
    """重复阈值距离应小于冲突阈值距离。"""
    assert DUPLICATE_MAX_DISTANCE < CONFLICT_MAX_DISTANCE


@pytest.mark.asyncio
async def test_check_content_duplicate():
    """高相似候选存在时应判定为 duplicate。"""
    svc = IngestionGateService(db=MagicMock())
    cand = MagicMock()
    cand.chunk_id = "existing-1"
    cand.distance = 0.2
    cand.similarity = 0.96
    cand.content_preview = "same text"

    with patch.object(svc, "_find_similar", AsyncMock(return_value=[cand])):
        result = await svc.check_content("kb1", "duplicate text")

    assert result.status == "duplicate"
    assert result.duplicate_of == "existing-1"


@pytest.mark.asyncio
async def test_check_content_allow_when_no_candidates():
    """无相似 chunk 时应 allow 入库。"""
    svc = IngestionGateService(db=MagicMock())
    with patch.object(svc, "_find_similar", AsyncMock(return_value=[])):
        result = await svc.check_content("kb1", "new unique content")
    assert result.status == "allow"


@pytest.mark.asyncio
async def test_check_content_conflict_zone_calls_llm():
    """冲突区候选应调用 LLM 判定并返回 conflict。"""
    svc = IngestionGateService(db=MagicMock())
    svc.llm_svc.mock_mode = False
    cand = MagicMock()
    cand.chunk_id = "c-old"
    cand.distance = 0.5
    cand.similarity = 0.875
    cand.content_preview = "old fact A"

    with patch.object(svc, "_find_similar", AsyncMock(return_value=[cand])):
        with patch.object(svc, "_llm_has_conflict", AsyncMock(return_value=True)):
            result = await svc.check_content("kb1", "contradicting fact B")

    assert result.status == "conflict"
    assert result.llm_calls == 1
