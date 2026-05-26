"""RAG 检索增强生成服务"""

import json
from typing import AsyncGenerator, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.chroma_client import get_collection
from ..models.chunk import Chunk
from .embedding_service import EmbeddingService
from .llm_service import LLMService
from .quality_service import QualityService, blend_retrieval_score


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
        """混合检索：向量相似度 + 关键词匹配（过滤已禁用的块）"""
        result_map: dict[str, dict] = {}
        active_map: dict[str, bool] = {}

        # —— 向量检索 ——
        query_embedding = self.embedding_service.embed_query(query)
        try:
            collection = get_collection(knowledge_base_id)
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k * 2,
            )
        except Exception:
            results = None

        if results and results.get("ids") and len(results["ids"][0]) > 0:
            chunk_ids = results["ids"][0]
            if db:
                db_result = await db.execute(
                    select(Chunk.id, Chunk.is_active).where(Chunk.id.in_(chunk_ids))
                )
                for row in db_result:
                    active_map[row.id] = row.is_active

            for i, chunk_id in enumerate(chunk_ids):
                if not active_map.get(chunk_id, True):
                    continue
                distance = results["distances"][0][i] if results.get("distances") else 0
                score = 0.7 * (1 - distance)
                if score > 0.2:
                    result_map[chunk_id] = {
                        "chunk_id": chunk_id,
                        "content": results["documents"][0][i],
                        "score": round(score, 4),
                        "chunk_index": results["metadatas"][0][i].get("chunk_index", 0),
                        "document_id": results["metadatas"][0][i].get("document_id", ""),
                    }

        # —— 关键词检索 ——
        if db and query:
            keywords = [w.strip() for w in query.replace(",", " ").replace(".", " ").split() if len(w.strip()) > 1]
            if keywords:
                from sqlalchemy import or_
                kw_conditions = [Chunk.content.contains(kw) for kw in keywords[:5]]
                kw_result = await db.execute(
                    select(Chunk)
                    .where(Chunk.knowledge_base_id == knowledge_base_id, Chunk.is_active.is_(True), or_(*kw_conditions))
                    .limit(top_k)
                )
                for chunk in kw_result.scalars().all():
                    if chunk.id not in result_map:
                        result_map[chunk.id] = {
                            "chunk_id": chunk.id,
                            "content": chunk.content,
                            "score": 0.5,
                            "chunk_index": chunk.chunk_index,
                            "document_id": chunk.document_id,
                        }

        sources = list(result_map.values())

        if sources and db:
            quality_svc = QualityService(db)
            qmap = await quality_svc.get_scores_map([s["chunk_id"] for s in sources])
            for s in sources:
                q = qmap.get(s["chunk_id"], 0.5)
                s["quality_score"] = q
                s["score"] = blend_retrieval_score(s["score"], q)

        sources = sorted(sources, key=lambda x: x["score"], reverse=True)[:top_k]

        # 热度统计
        if sources and db:
            try:
                for s in sources:
                    chunk = await db.get(Chunk, s["chunk_id"])
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
