"""RAG 检索增强生成服务"""

import json
from typing import AsyncGenerator, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.chroma_client import get_collection
from ..models.chunk import Chunk
from .embedding_service import EmbeddingService
from .llm_service import LLMService


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
        self.embedding_service = EmbeddingService()
        self.llm_service = LLMService()

    async def retrieve(
        self, knowledge_base_id: str, query: str, top_k: int = 5, db: AsyncSession = None
    ) -> List[Dict]:
        """检索相关知识块（过滤已禁用的块）"""
        query_embedding = self.embedding_service.embed_query(query)
        try:
            collection = get_collection(knowledge_base_id)
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k * 3,
            )
        except Exception:
            return []

        sources = []
        if results.get("ids") and len(results["ids"][0]) > 0:
            chunk_ids = results["ids"][0]

            # 过滤已禁用的块
            active_map = {}
            if db:
                db_result = await db.execute(
                    select(Chunk.id, Chunk.is_active).where(Chunk.id.in_(chunk_ids))
                )
                for row in db_result:
                    active_map[row.id] = row.is_active

            count = 0
            for i, chunk_id in enumerate(chunk_ids):
                if not active_map.get(chunk_id, True):
                    continue
                distance = results["distances"][0][i] if results.get("distances") else 0
                score = 1 - distance
                if score > 0.3:
                    sources.append({
                        "chunk_id": chunk_id,
                        "content": results["documents"][0][i],
                        "score": round(score, 4),
                        "chunk_index": results["metadatas"][0][i].get("chunk_index", 0),
                        "document_id": results["metadatas"][0][i].get("document_id", ""),
                    })
                    count += 1
                    if count >= top_k:
                        break

            # 热度统计：递增命中次数
            if sources and db:
                try:
                    hit_ids = [s["chunk_id"] for s in sources]
                    for chunk_id in hit_ids:
                        chunk = await db.get(Chunk, chunk_id)
                        if chunk:
                            chunk.hit_count = (chunk.hit_count or 0) + 1
                    await db.commit()
                except Exception:
                    pass

        return sources

    async def generate(
        self, knowledge_base_id: str, query: str, history: List[Dict],
        top_k: int = 5, db: AsyncSession = None,
    ) -> AsyncGenerator[str, None]:
        """RAG 生成（流式）"""
        sources = await self.retrieve(knowledge_base_id, query, top_k, db)

        context = "\n\n---\n\n".join([
            f"[来源 {i+1}] {s['content']}" for i, s in enumerate(sources)
        ]) if sources else "知识库中暂无相关内容"

        messages = [{"role": "system", "content": self.SYSTEM_PROMPT.format(context=context)}]
        for msg in history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": query})

        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

        async for chunk in self.llm_service.chat_stream(messages):
            yield chunk
