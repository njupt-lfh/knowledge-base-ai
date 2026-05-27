"""Phase 3.1 轻量知识图谱验收 — 零 Chat API（LLM_MOCK_MODE=true）"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ["LLM_MOCK_MODE"] = "true"


async def main() -> int:
    from app.core.database import async_session, init_db
    from app.models.chunk import Chunk
    from app.models.document import Document
    from app.models.knowledge_base import KnowledgeBase
    from app.services.agent_orchestrator import AgentOrchestrator
    from app.services.graph_retriever import GraphRetriever
    from app.services.graph_store_service import graph_snapshot, sync_chunk_graph

    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb-p3-{suffix}"
    doc_id = f"d-p3-{suffix}"
    chunk_id = f"c-p3-{suffix}"
    content = "知识图谱与向量检索是RAG的两种路径，知识图谱属于关系型检索。"

    async with async_session() as db:
        db.add(KnowledgeBase(id=kb_id, name="p3", embedding_model="m", chunk_size=500, chunk_overlap=50))
        db.add(Document(id=doc_id, knowledge_base_id=kb_id, filename="m", file_type="manual", status="completed"))
        db.add(
            Chunk(
                id=chunk_id,
                document_id=doc_id,
                knowledge_base_id=kb_id,
                content=content,
                chunk_index=0,
                char_count=len(content),
            )
        )
        await db.commit()

        n = await sync_chunk_graph(db, kb_id, chunk_id, doc_id, content)
        assert n >= 1, "triple sync failed"

        snap = await graph_snapshot(db, kb_id)
        assert snap["relation_count"] >= 1, "empty graph snapshot"

        gr = GraphRetriever()
        sources, paths = await gr.search(db, kb_id, "知识图谱与向量检索的关系", top_k=5)
        assert sources and sources[0]["chunk_id"] == chunk_id, "graph retrieve failed"

        from unittest.mock import AsyncMock, patch

        orch = AgentOrchestrator()
        with patch.object(orch.hybrid, "search", new=AsyncMock(return_value=[])):
            run = await orch.run(db, kb_id, "知识图谱与向量检索的区别是什么？", top_k=5)
            assert run.route == "relational"
            assert run.graph_used
            assert any(s["chunk_id"] == chunk_id for s in run.sources)

    print("PASS: Phase 3.1 lightweight knowledge graph — ingest + retrieve + agent relational")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
