"""RAG 检索增强生成服务（Phase 2.2）。

职责：
    对外暴露统一的 RAG 入口，将用户查询委托给 AgentOrchestrator 完成
    「路由 → 混合检索 → CRAG 充分性评估 → LLM 流式生成」全流程。

在流水线中的位置：
    ChatService.chat_stream → RAGService.generate → AgentOrchestrator.generate_stream

依赖服务：
    - HybridRetriever：向量 + FTS5 混合检索（评测脚本亦可通过 retrieve 直接调用）
    - AgentOrchestrator：Agentic-lite 编排（Router / CRAG / 图谱 / SIM-RAG）
"""

import json
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from .agent_orchestrator import AgentOrchestrator
from .hybrid_retriever import HybridRetriever


class RAGService:
    """RAG 门面类：封装检索、上下文压缩与流式生成。"""

    SYSTEM_PROMPT = """你是一个基于知识库的智能助手。请根据提供的知识库内容回答用户的问题。

规则：
1. 回答前请先判断：提供的资料是否足以准确回答？若不足，必须回复「目前知识库中暂无相关信息」，不要猜测、推理或编造。
2. 若知识库中有相关内容，请基于知识库内容准确回答，并在回答中注明引用的知识点（[来源 N]）。
3. 先给 1 句直接答案，再最多 3 条要点；禁止冗长复述 context，禁止引入 context 外的术语。
4. 如果用户的问题涉及多个知识点，请综合分析后回答，但仍须控制在简洁范围内。

知识库内容：
{context}"""

    def __init__(self):
        self.hybrid = HybridRetriever()
        self.agent = AgentOrchestrator()

    async def retrieve(
        self, knowledge_base_id: str, query: str, top_k: int = 5, db: AsyncSession = None
    ) -> list[dict]:
        """Hybrid 检索（评测脚本兼容路径，不经过 Agent/CRAG）。

        参数:
            knowledge_base_id: 知识库 ID
            query: 用户查询
            top_k: 返回条数上限
            db: 异步数据库会话

        返回:
            检索来源列表，每项含 chunk_id、content、score 等字段
        """
        if not db:
            return []
        sources = await self.hybrid.search(db, knowledge_base_id, query, top_k=top_k)

        # 命中计数：供质量分与治理统计使用
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
        """选择性压缩 context，控制 token 预算（extractive 截断）。

        参数:
            sources: 检索来源列表
            max_chars: 上下文最大字符数

        返回:
            格式化后的上下文字符串，供 SYSTEM_PROMPT 填充
        """
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
        """Agentic-lite RAG 生成（SSE 流式）。

        参数:
            knowledge_base_id: 知识库 ID
            query: 当前用户问题
            history: 历史消息列表 [{role, content}, ...]
            top_k: 检索条数
            db: 异步数据库会话

        Yields:
            SSE 格式事件字符串（agent_meta / sources / text / done）
        """
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
