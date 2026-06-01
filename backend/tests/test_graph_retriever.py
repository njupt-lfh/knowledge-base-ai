"""GraphRetriever 与 RRF 融合测试

验证内容：
  - GraphRetriever 检索与 RRF 融合

运行方式（在 backend 目录）:
  pytest tests/test_graph_retriever.py -v

预期结果：全部用例通过。
"""

from __future__ import annotations

import uuid

import pytest
from app.services.graph_retriever import GraphRetriever
from app.services.hybrid_retriever import merge_source_lists


def test_merge_source_lists_rrf():
    """验证 RRF 融合排序。"""
    hybrid = [
        {"chunk_id": "a", "content": "A", "score": 0.9, "source": "hybrid"},
        {"chunk_id": "b", "content": "B", "score": 0.8, "source": "hybrid"},
    ]
    graph = [
        {"chunk_id": "b", "content": "B", "score": 0.95, "source": "graph"},
        {"chunk_id": "c", "content": "C", "score": 0.7, "source": "graph"},
    ]
    merged = merge_source_lists([graph, hybrid], top_k=3)
    ids = [m["chunk_id"] for m in merged]
    assert "b" in ids
    assert merged[0]["source"] in ("graph", "graph+hybrid", "hybrid+graph")


@pytest.mark.asyncio
async def test_graph_retriever_search():
    """验证图谱相关检索/存储。"""
    from app.core.database import async_session, init_db
    from app.models.chunk import Chunk
    from app.models.document import Document
    from app.models.knowledge_base import KnowledgeBase
    from app.services.graph_store_service import sync_chunk_graph

    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb-gr-{suffix}"
    doc_id = f"d-gr-{suffix}"
    chunk_id = f"c-gr-{suffix}"
    content = "React与Vue是前端框架，React属于JavaScript生态。"

    async with async_session() as db:
        db.add(
            KnowledgeBase(id=kb_id, name="g", embedding_model="m", chunk_size=500, chunk_overlap=50)
        )
        db.add(
            Document(
                id=doc_id,
                knowledge_base_id=kb_id,
                filename="t",
                file_type="txt",
                status="completed",
            )
        )
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
        await sync_chunk_graph(db, kb_id, chunk_id, doc_id, content)

        retriever = GraphRetriever()
        sources, paths = await retriever.search(db, kb_id, "React与Vue的区别", top_k=3)
        assert sources
        assert sources[0]["chunk_id"] == chunk_id
        assert sources[0]["source"] == "graph"
        assert paths
