import json

import pytest
from app.services.llm_service import LLMService


@pytest.mark.asyncio
async def test_chat_stream_mock_mode():
    svc = LLMService()
    assert svc.mock_mode is True
    events = []
    async for event in svc.chat_stream([{"role": "user", "content": "hi"}]):
        events.append(event)
    assert len(events) >= 2
    payload = json.loads(events[0].removeprefix("data: ").strip())
    assert payload["type"] == "text"
    assert "Mock" in payload["content"]
