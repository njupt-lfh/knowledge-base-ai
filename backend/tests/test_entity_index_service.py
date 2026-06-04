"""Phase 3b entity_index_service 单元测试。"""

from __future__ import annotations

import uuid

import pytest
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.services.entity_index_service import (
    build_entity_index,
    build_entity_index_from_relations,
    extract_query_entities,
    normalize_graph_mode,
    rank_chunks_linear,
    search_entity_index,
)
from app.services.graph_store_service import sync_chunk_graph


async def _cleanup_test_kb(kb_id: str) -> None:
    """删除测试知识库及其关联数据。"""
    from app.core.database import async_session

    async with async_session() as db:
        for t, col in [
            ("chunks", "knowledge_base_id"),
            ("documents", "knowledge_base_id"),
            ("kg_relations", "knowledge_base_id"),
        ]:
            await db.execute(
                __import__("sqlalchemy").text(f"DELETE FROM {t} WHERE {col}=:kid"),
                {"kid": kb_id},
            )
        await db.execute(
            __import__("sqlalchemy").text("DELETE FROM knowledge_bases WHERE id=:kid"),
            {"kid": kb_id},
        )
        await db.commit()


def test_normalize_graph_mode():
    assert normalize_graph_mode("linear") == "linear"
    assert normalize_graph_mode("UNKNOWN") == "lite"


def test_build_entity_index_cooccurrence():
    from app.models.kg_relation import KgRelation

    rel = KgRelation(
        knowledge_base_id="kb",
        chunk_id="c1",
        document_id="d1",
        subject="React",
        predicate="属于",
        object_entity="JavaScript",
    )
    snap = build_entity_index_from_relations("kb", [rel])
    assert "c1" in snap.entity_to_chunks["React"]
    assert "JavaScript" in snap.cooccurrence.get("React", set())


def test_rank_chunks_linear_two_hop():
    from app.models.kg_relation import KgRelation

    rels = [
        KgRelation(
            knowledge_base_id="kb",
            chunk_id="c1",
            document_id="d1",
            subject="Alpha",
            predicate="关联",
            object_entity="Beta",
        ),
        KgRelation(
            knowledge_base_id="kb",
            chunk_id="c2",
            document_id="d1",
            subject="Gamma",
            predicate="关联",
            object_entity="Beta",
        ),
    ]
    snap = build_entity_index_from_relations("kb", rels)
    scores, paths = rank_chunks_linear(snap, ["Alpha", "Beta"], top_k=5)
    assert "c1" in scores
    assert any(p.get("hop") == 2 for p in paths)


@pytest.mark.asyncio
async def test_search_entity_index_integration():
    from app.core.database import async_session, init_db

    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb-linear-{suffix}"
    doc_id = f"d-linear-{suffix}"
    chunk_id = f"c-linear-{suffix}"
    content = "React与Vue是前端框架，React属于JavaScript生态。"

    try:
        async with async_session() as db:
            db.add(
                KnowledgeBase(
                    id=kb_id, name="g", embedding_model="m", chunk_size=500, chunk_overlap=50
                )
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
            await sync_chunk_graph(db, kb_id, chunk_id, doc_id, content)

            snap = await build_entity_index(db, kb_id)
            assert snap.entity_names
            seeds = extract_query_entities("React与Vue的区别", snap.entity_names)
            assert seeds

            sources, paths = await search_entity_index(db, kb_id, "React与Vue的区别", top_k=3)
            assert sources
            assert sources[0]["chunk_id"] == chunk_id
            assert sources[0]["source"] == "graph-linear"
            assert paths
    finally:
        await _cleanup_test_kb(kb_id)


@pytest.mark.asyncio
async def test_graph_retriever_linear_mode():
    from app.core.database import async_session, init_db
    from app.services.graph_retriever import GraphRetriever

    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb-gr-lin-{suffix}"
    doc_id = f"d-gr-lin-{suffix}"
    chunk_id = f"c-gr-lin-{suffix}"
    content = "深度学习与机器学习是人工智能分支，深度学习属于机器学习。"

    try:
        async with async_session() as db:
            db.add(
                KnowledgeBase(
                    id=kb_id, name="g", embedding_model="m", chunk_size=500, chunk_overlap=50
                )
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
            await sync_chunk_graph(db, kb_id, chunk_id, doc_id, content)

            retriever = GraphRetriever()
            sources, paths = await retriever.search(
                db,
                kb_id,
                "深度学习与机器学习的关系",
                top_k=3,
                graph_mode="linear",
            )
            assert sources
            assert sources[0].get("graph_mode") == "linear"
            assert paths
    finally:
        await _cleanup_test_kb(kb_id)
