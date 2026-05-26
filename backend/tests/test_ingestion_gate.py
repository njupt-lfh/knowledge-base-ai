from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ingestion_gate_service import (
    CONFLICT_MAX_DISTANCE,
    DUPLICATE_MAX_DISTANCE,
    ChunkGateResult,
    IngestionGateService,
    distance_to_similarity,
)


def test_distance_to_similarity():
    assert distance_to_similarity(0.0) == 1.0
    assert distance_to_similarity(DUPLICATE_MAX_DISTANCE) == pytest.approx(0.92, abs=0.01)


def test_threshold_ordering():
    assert DUPLICATE_MAX_DISTANCE < CONFLICT_MAX_DISTANCE


@pytest.mark.asyncio
async def test_check_content_duplicate():
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
    svc = IngestionGateService(db=MagicMock())
    with patch.object(svc, "_find_similar", AsyncMock(return_value=[])):
        result = await svc.check_content("kb1", "new unique content")
    assert result.status == "allow"


@pytest.mark.asyncio
async def test_check_content_conflict_zone_calls_llm():
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
