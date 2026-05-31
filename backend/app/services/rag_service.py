"""RAG 检索增强生成服务 — Phase 2.2 使用 AgentOrchestrator（Hybrid + CRAG-lite）"""

import json
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from .agent_orchestrator import AgentOrchestrator
from .hybrid_retriever import HybridRetriever


class RAGService:
    SYSTEM_PROMPT = """你是一个基于知识库的智能助手。请根据提供的知识库内容回答用户的问题。

规则：
1. 如果知识库中有相关内容，请基于知识库内容准确回答，并在回答中注明引用的知识点。
2. 如果知识库中没有相关内容，请明确告知用户"目前知识库中暂无相关信息"。
3. 回答要简洁、准确，避免编造信息。
4. 如果用户的问题涉及多个知识点，请综合分析后回答。

知识库内容：
{context}"""

    def __init__(self):
        self.hybrid = HybridRetriever()
        self.agent = AgentOrchestrator()

    async def retrieve(
        self, knowledge_base_id: str, query: str, top_k: int = 5, db: AsyncSession = None
    ) -> list[dict]:
        """Hybrid 检索（评测脚本兼容路径）。"""
        if not db:
            return []
        sources = await self.hybrid.search(db, knowledge_base_id, query, top_k=top_k)

        if sources:
            try:
                from ..models.chunk import Chunk

                for s in sources:
                    chunk = await db.get(Chunk, s["chunk_id"])
                    if chunk:
                        chunk.hit_count = (chunk.hit_count or 0) + 1
                await db.commit()
            except Exception:
                pass

        return sources

    @staticmethod
    def compress_context(sources: list[dict], max_chars: int = 4500) -> str:
        """选择性压缩 context，控制 token 预算（extractive 截断）。"""
        if not sources:
            return "知识库中暂无相关内容"
        parts: list[str] = []
        used = 0
        for i, s in enumerate(sources):
            header = f"[来源 {i + 1}] "
            body = s.get("content", "")
            budget = max_chars - used - len(header) - 8
            if budget <= 0:
                break
            if len(body) > budget:
                body = body[:budget] + "…"
            parts.append(f"{header}{body}")
            used += len(parts[-1]) + 2
        return "\n\n---\n\n".join(parts)

    async def generate(
        self,
        knowledge_base_id: str,
        query: str,
        history: list[dict],
        top_k: int = 5,
        db: AsyncSession = None,
    ) -> AsyncGenerator[str, None]:
        """Agentic-lite RAG 生成（流式）。"""
        if not db:
            yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        async for event in self.agent.generate_stream(
            db,
            knowledge_base_id,
            query,
            history,
            top_k=top_k,
            system_prompt_template=self.SYSTEM_PROMPT,
            compress_context=self.compress_context,
        ):
            yield event
