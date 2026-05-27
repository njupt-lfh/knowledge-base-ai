"""LLM 调用服务 — 火山引擎豆包 Chat API"""

import json
from typing import AsyncGenerator, Dict, List

import httpx

from ..core.config import settings


class LLMService:
    def __init__(self, model_name: str | None = None):
        self.api_key = settings.VOLCENGINE_API_KEY
        self.base_url = settings.VOLCENGINE_BASE_URL
        self.model_name = model_name or settings.VOLCENGINE_LLM_MODEL
        self.mock_mode = settings.LLM_MOCK_MODE

    async def chat_stream(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        if self.mock_mode:
            mock_reply = "Mock 模式已启用。请在 .env 中设置 LLM_MOCK_MODE=false"
            yield f"data: {json.dumps({'type': 'text', 'content': mock_reply})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_name,
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

    async def chat_completion(
        self,
        messages: List[Dict],
        *,
        temperature: float = 0.3,
        max_tokens: int = 512,
    ) -> str:
        """非流式补全，供入库冲突检测等场景使用。"""
        if self.mock_mode:
            return '{"conflict": false, "reason": "mock mode"}'

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "stream": False,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
