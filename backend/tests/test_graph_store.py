"""Phase 3 轻量知识图谱 — 单元测试"""

from __future__ import annotations

import uuid

import pytest
from app.services.entity_extraction_service import extract_triples_from_chunk
from app.services.graph_store_service import (
    build_networkx_graph,
    expand_graph_paths,
    link_entities_in_query,
    sync_chunk_graph,
)


@pytest.mark.asyncio
async def test_mock_extract_triples():
    triples = await extract_triples_from_chunk("Python和Java是两种编程语言，Python属于脚本语言。")
    assert len(triples) >= 1
    assert any(t["subject"] in ("Python", "Java") or "Python" in t["subject"] for t in triples)


@pytest.mark.asyncio
async def test_sync_and_expand_graph():
    from app.core.database import async_session, init_db
    from app.models.chunk import Chunk
    from app.models.document import Document
    from app.models.knowledge_base import KnowledgeBase

    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb-graph-{suffix}"
    doc_id = f"d-graph-{suffix}"
    chunk_id = f"c-graph-{suffix}"
    content = "深度学习与机器学习是人工智能的核心分支，深度学习属于机器学习。"

    async with async_session() as db:
        db.add(
            KnowledgeBase(id=kb_id, name="g", embedding_model="m", chunk_size=500, chunk_overlap=50)
        )
        db.add(
            Document(
                id=doc_id,
                knowledge_base_id=kb_id,
                filename="t.txt",
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

        n = await sync_chunk_graph(db, kb_id, chunk_id, doc_id, content)
        assert n >= 1

        graph = await build_networkx_graph(db, kb_id)
        assert graph.number_of_edges() >= 1

        seeds = link_entities_in_query("深度学习与机器学习的关系", await _entity_names(db, kb_id))
        assert seeds
        scores, paths = expand_graph_paths(graph, seeds, max_hops=2)
        assert chunk_id in scores
        assert paths


async def _entity_names(db, kb_id):
    from app.services.graph_store_service import list_entity_names

    return await list_entity_names(db, kb_id)
