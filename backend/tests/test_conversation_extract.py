from unittest.mock import AsyncMock, patch

import pytest

from app.services.conversation_extract_service import ConversationExtractService


def test_source_in_dialog():
    assert ConversationExtractService._source_in_dialog(
        "Python 是一种高级语言",
        "补充：Python 是一种高级语言",
        "好的",
    )


def test_pack_suggested():
    raw = ConversationExtractService.pack_suggested(
        {"title": "T", "content": "C", "tags": ["a"], "entities": [], "gap_type": "USER_PROVIDED"}
    )
    assert "USER_PROVIDED" in raw


@pytest.mark.asyncio
async def test_extract_mock_mode_requires_source():
    svc = ConversationExtractService()
    svc.llm.mock_mode = True
    out = await svc.extract_from_turn(
        "我们公司年假是15天",
        "好的，已记录",
        hint_gap_type="USER_PROVIDED",
    )
    assert out is not None
    assert out.get("source_ref")


@pytest.mark.asyncio
async def test_extract_rejects_without_source_in_dialog():
    svc = ConversationExtractService()
    svc.llm.mock_mode = False
    with patch.object(
        svc.llm,
        "chat_completion",
        AsyncMock(
            return_value='{"has_knowledge":true,"gap_type":"USER_PROVIDED","title":"x","content":"y","tags":[],"entities":[],"source_ref":"完全不相关的引用"}'
        ),
    ):
        out = await svc.extract_from_turn("真实用户句子", "助手回复")
    assert out is None
