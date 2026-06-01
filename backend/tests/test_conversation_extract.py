"""ConversationExtractService 对话提炼单元测试。

验证内容：
  - 对话提炼 source_ref 约束与 pack_suggested

运行方式（在 backend 目录）:
  pytest tests/test_conversation_extract.py -v

预期结果：全部用例通过。
"""

from unittest.mock import AsyncMock, patch

import pytest
from app.services.conversation_extract_service import ConversationExtractService


def test_source_in_dialog():
    """source_ref 出现在用户或助手对话中时应返回 True。"""
    assert ConversationExtractService._source_in_dialog(
        "Python 是一种高级语言",
        "补充：Python 是一种高级语言",
        "好的",
    )


def test_pack_suggested():
    """pack_suggested 应将 gap_type 等字段序列化为 JSON 字符串。"""
    raw = ConversationExtractService.pack_suggested(
        {"title": "T", "content": "C", "tags": ["a"], "entities": [], "gap_type": "USER_PROVIDED"}
    )
    assert "USER_PROVIDED" in raw


@pytest.mark.asyncio
async def test_extract_mock_mode_requires_source():
    """mock 模式提炼结果必须包含 source_ref。"""
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
    """LLM 返回的 source_ref 不在对话中时应拒绝提炼（返回 None）。"""
    svc = ConversationExtractService()
    svc.llm.mock_mode = False
    # mock LLM 返回不在对话中的 source_ref
    with patch.object(
        svc.llm,
        "chat_completion",
        AsyncMock(
            return_value='{"has_knowledge":true,"gap_type":"USER_PROVIDED","title":"x","content":"y","tags":[],"entities":[],"source_ref":"完全不相关的引用"}'
        ),
    ):
        out = await svc.extract_from_turn("真实用户句子", "助手回复")
    assert out is None
