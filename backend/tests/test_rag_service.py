from unittest.mock import AsyncMock, patch

import pytest
from app.models.chunk import Chunk
from app.services.rag_service import RAGService
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_retrieve_hybrid_path():
    rag = RAGService()
    chunk_id = "test-chunk-id-001"
    chunk = Chunk(
        id=chunk_id,
        document_id="doc-1",
        knowledge_base_id="kb-test",
        content="RAG 是 Retrieval Augmented Generation",
        chunk_index=0,
        char_count=40,
        is_active=True,
    )

    db = AsyncMock(spec=AsyncSession)

    async def fake_search(db_, kb_id, query, top_k=None):
        return [
            {
                "chunk_id": chunk_id,
                "content": chunk.content,
                "chunk_index": 0,
                "document_id": "doc-1",
                "score": 0.8,
                "rrf_score": 0.8,
            }
        ]

    db.get = AsyncMock(return_value=chunk)
    db.commit = AsyncMock()

    with patch.object(rag.hybrid, "search", side_effect=fake_search):
        sources = await rag.retrieve("kb-test", "什么是 RAG", top_k=5, db=db)

    assert len(sources) == 1
    assert sources[0]["chunk_id"] == chunk_id


@pytest.mark.asyncio
async def test_retrieve_empty_without_db():
    rag = RAGService()
    sources = await rag.retrieve("kb-test", "q", top_k=5, db=None)
    assert sources == []


@pytest.mark.asyncio
async def test_retrieve_returns_empty_when_hybrid_empty():
    rag = RAGService()
    db = AsyncMock(spec=AsyncSession)
    with patch.object(rag.hybrid, "search", AsyncMock(return_value=[])):
        sources = await rag.retrieve("kb-test", "q", top_k=5, db=db)
    assert sources == []
