"""Phase 4.3 SIM-RAG 验收"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ["LLM_MOCK_MODE"] = "true"
os.environ["SIM_RAG_ENABLED"] = "true"

from app.core.config import settings  # noqa: E402

settings.SIM_RAG_ENABLED = True


async def main() -> int:
    from app.core.database import async_session, init_db
    from app.models.chunk import Chunk
    from app.models.document import Document
    from app.models.knowledge_base import KnowledgeBase
    from app.services.agent_orchestrator import AgentOrchestrator
    from app.services.sim_rag_service import decompose_sub_queries

    qs = decompose_sub_queries("模块A是什么？模块B如何配置？")
    assert len(qs) >= 2, "decompose failed"

    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb-p43-{suffix}"
    doc_id = f"d-p43-{suffix}"
    chunk_a = f"c-a-{suffix}"
    chunk_b = f"c-b-{suffix}"

    async with async_session() as db:
        db.add(KnowledgeBase(id=kb_id, name="p43", embedding_model="m", chunk_size=500, chunk_overlap=50))
        db.add(Document(id=doc_id, knowledge_base_id=kb_id, filename="m", file_type="manual", status="completed"))
        db.add(
            Chunk(
                id=chunk_a,
                document_id=doc_id,
                knowledge_base_id=kb_id,
                content="模块A是检索网关，负责路由与鉴权。",
                chunk_index=0,
                char_count=20,
            )
        )
        db.add(
            Chunk(
                id=chunk_b,
                document_id=doc_id,
                knowledge_base_id=kb_id,
                content="模块B的配置在 config 页面，包含 chunk_size。",
                chunk_index=1,
                char_count=30,
            )
        )
        await db.commit()

    orch = AgentOrchestrator()

    async def fake_retrieve(db, kb_id, query, *, route, top_k):
        if "A" in query:
            src = [{"chunk_id": chunk_a, "content": "模块A是检索网关", "score": 0.9, "source": "vector"}]
        else:
            src = [
                {
                    "chunk_id": chunk_b,
                    "content": "模块B的配置在 config 页面",
                    "score": 0.88,
                    "source": "vector",
                }
            ]
        return src, []

    orch._retrieve = fake_retrieve  # type: ignore[method-assign]

    from app.services.sim_rag_service import sim_rag_retrieve

    async with async_session() as db:
        sim = await sim_rag_retrieve(
            db,
            kb_id,
            "模块A是什么？模块B如何配置？",
            route="factual",
            hybrid=orch.hybrid,
            retrieve_fn=orch._retrieve,
            top_k=10,
        )
        assert sim is not None
        assert len(sim.sub_queries) >= 2
        ids = {s["chunk_id"] for s in sim.sources}
        assert chunk_a in ids and chunk_b in ids, f"sim merge ids={ids}"

        run = await orch.run(db, kb_id, "模块A是什么？模块B如何配置？", top_k=10)
        assert run.sim_rag_used

    print("PASS: Phase 4.3 SIM-RAG — decompose + multi-retrieve + coverage critic")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
