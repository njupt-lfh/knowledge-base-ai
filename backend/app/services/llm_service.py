"""LLM 调用服务"""

import json
from typing import AsyncGenerator, List, Dict

from ..core.config import settings


class LLMService:
    """大模型调用服务 — 基于火山引擎豆包 Chat API"""

    MODEL_NAME = "doubao-seed-1-6-flash-250828"
    BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

    def __init__(self):
        self.api_key = settings.VOLCENGINE_API_KEY
        self.mock_mode = settings.LLM_MOCK_MODE

    async def chat_stream(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        if self.mock_mode:
            mock_reply = "Mock 模式已启用。请在 .env 中设置 LLM_MOCK_MODE=false 并填写 VOLCENGINE_API_KEY 以启用真实 AI 对话。"
            yield f"data: {json.dumps({'type': 'text', 'content': mock_reply})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # TODO: 接入火山引擎流式 API
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self.BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.MODEL_NAME,
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.7,
                    "max_tokens": 2048,
                },
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            yield f"data: {json.dumps({'type': 'done'})}\n\n"
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield f"data: {json.dumps({'type': 'text', 'content': content})}\n\n"
                        except json.JSONDecodeError:
                            continue
