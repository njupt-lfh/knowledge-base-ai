"""LLMService mock 模式单元测试。

验证内容：
  - chat_stream 在 mock 模式下返回 text 事件且含 Mock 字样

运行方式（在 backend 目录）:
  pytest tests/test_llm_service.py -v

预期结果：全部用例通过。
"""

import json

import pytest
from app.services.llm_service import LLMService


@pytest.mark.asyncio
async def test_chat_stream_mock_mode():
    """mock 模式流式输出应至少 2 个 SSE 事件，首条为 text 类型。"""
    svc = LLMService()
    assert svc.mock_mode is True
    events = []
    async for event in svc.chat_stream([{"role": "user", "content": "hi"}]):
        events.append(event)
    assert len(events) >= 2
    payload = json.loads(events[0].removeprefix("data: ").strip())
    assert payload["type"] == "text"
    assert "Mock" in payload["content"]
