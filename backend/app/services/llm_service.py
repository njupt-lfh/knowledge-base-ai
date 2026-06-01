"""LLM 调用服务（火山引擎豆包 Chat API）。

职责：
    封装流式与非流式 Chat Completions，供 RAG 回答、图谱抽取、
    冲突检测、Vision 描述等场景使用。

在流水线中的位置：
    AgentOrchestrator、entity_extraction_service、ingestion_gate_service、
    vision_caption_service、conversation_extract_service

依赖：无（底层 httpx + 火山 API）
"""

import json
from collections.abc import AsyncGenerator

import httpx

from ..core.config import settings


class LLMService:
    """豆包 LLM 客户端：支持流式 chat_stream 与非流式 chat_completion。"""

    def __init__(self, model_name: str | None = None):
        self.api_key = settings.VOLCENGINE_API_KEY
        self.base_url = settings.VOLCENGINE_BASE_URL
        self.model_name = model_name or settings.VOLCENGINE_LLM_MODEL
        self.mock_mode = settings.LLM_MOCK_MODE

    async def chat_stream(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """流式对话，输出 SSE 格式 text/done 事件。

        参数:
            messages: OpenAI 格式消息列表

        Yields:
            SSE 字符串（type=text 或 type=done）
        """
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
        messages: list[dict],
        *,
        temperature: float = 0.3,
        max_tokens: int = 512,
    ) -> str:
        """非流式补全，供入库冲突检测、图谱抽取等场景使用。

        参数:
            messages: 消息列表
            temperature: 采样温度
            max_tokens: 最大生成 token 数

        返回:
            助手回复文本

        Raises:
            httpx.HTTPStatusError: API 返回非 2xx
        """
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
