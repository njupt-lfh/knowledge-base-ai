from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.feedback_service import FeedbackService


@pytest.mark.asyncio
async def test_resolve_chunk_ids_prefers_chunk_ids_list():
    svc = FeedbackService(db=MagicMock())
    msg = MagicMock()
    msg.sources = [
        {"chunk_id": "c1", "score": 0.8},
        {"chunk_id": "c2", "score": 0.7},
    ]
    ids = await svc._resolve_chunk_ids(
        msg, explicit_chunk_id="c99", explicit_chunk_ids=["c2", "c1", "c2"]
    )
    assert ids == ["c2", "c1"]


@pytest.mark.asyncio
async def test_resolve_chunk_ids_all_sources_when_no_explicit():
    svc = FeedbackService(db=MagicMock())
    msg = MagicMock()
    msg.sources = [{"chunk_id": "a"}, {"chunk_id": "b"}]
    ids = await svc._resolve_chunk_ids(msg, None, None)
    assert ids == ["a", "b"]


@pytest.mark.asyncio
async def test_create_feedback_updates_all_chunks():
    svc = FeedbackService(db=MagicMock())
    msg = MagicMock()
    msg.conversation_id = "conv1"
    msg.content = "answer"
    msg.sources = [{"chunk_id": "c1"}, {"chunk_id": "c2"}]

    svc.db.get = AsyncMock(return_value=msg)
    svc.db.add = MagicMock()
    svc.db.commit = AsyncMock()
    svc.db.refresh = AsyncMock()
    svc._find_user_query = AsyncMock(return_value="question")

    with patch.object(svc, "_resolve_chunk_ids", AsyncMock(return_value=["c1", "c2"])):
        with patch("app.services.feedback_service.QualityService") as QCls:
            quality = QCls.return_value
            quality.apply_feedback = AsyncMock()
            with patch("app.services.feedback_service.GapService") as GCls:
                gap_svc = GCls.return_value
                gap_svc.create_gap = AsyncMock()
                await svc.create_feedback(
                    "kb1",
                    message_id="m1",
                    feedback_type="dislike",
                    chunk_ids=["c1", "c2"],
                )
                quality.apply_feedback.assert_called_once_with(["c1", "c2"], "dislike")
