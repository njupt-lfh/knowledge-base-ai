from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk
from app.services.rag_service import RAGService


@pytest.mark.asyncio
async def test_retrieve_vector_path(monkeypatch):
    rag = RAGService()
    chunk_id = "test-chunk-id-001"

    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "ids": [[chunk_id]],
        "documents": [["RAG 是 Retrieval Augmented Generation"]],
        "distances": [[0.05]],
        "metadatas": [[{"chunk_index": 0, "document_id": "doc-1"}]],
    }

    class _Row:
        def __init__(self, cid: str, active: bool):
            self.id = cid
            self.is_active = active

    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter([_Row(chunk_id, True)])

    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=mock_result)
    db.get = AsyncMock(return_value=None)
    db.commit = AsyncMock()

    with (
        patch.object(rag.embedding_service, "embed_query", return_value=[0.0] * 256),
        patch("app.services.rag_service.get_collection", return_value=mock_collection),
    ):
        sources = await rag.retrieve("kb-test", "什么是 RAG", top_k=5, db=db)

    assert len(sources) >= 1
    assert sources[0]["chunk_id"] == chunk_id
    assert "Retrieval" in sources[0]["content"]


@pytest.mark.asyncio
async def test_retrieve_chroma_failure_keyword_fallback(monkeypatch):
    rag = RAGService()
    chunk = Chunk(
        id="kw-chunk-1",
        document_id="doc-1",
        knowledge_base_id="kb-test",
        content="dotenv 用于读取环境变量",
        chunk_index=0,
        char_count=20,
        is_active=True,
    )

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [chunk]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=mock_result)
    db.get = AsyncMock(return_value=chunk)
    db.commit = AsyncMock()

    with (
        patch.object(rag.embedding_service, "embed_query", return_value=[0.0] * 256),
        patch("app.services.rag_service.get_collection", side_effect=RuntimeError("chroma down")),
    ):
        sources = await rag.retrieve("kb-test", "dotenv 作用", top_k=5, db=db)

    assert any(s["chunk_id"] == "kw-chunk-1" for s in sources)


@pytest.mark.asyncio
async def test_retrieve_filters_inactive_chunks():
    rag = RAGService()
    active_id, inactive_id = "active-chunk", "inactive-chunk"

    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "ids": [[active_id, inactive_id]],
        "documents": [["active text", "inactive text"]],
        "distances": [[0.05, 0.05]],
        "metadatas": [[{"chunk_index": 0, "document_id": "d1"}, {"chunk_index": 1, "document_id": "d1"}]],
    }

    class _Row:
        def __init__(self, cid: str, active: bool):
            self.id = cid
            self.is_active = active

    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter([_Row(active_id, True), _Row(inactive_id, False)])

    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=mock_result)
    db.get = AsyncMock(return_value=None)
    db.commit = AsyncMock()

    with (
        patch.object(rag.embedding_service, "embed_query", return_value=[0.0] * 256),
        patch("app.services.rag_service.get_collection", return_value=mock_collection),
    ):
        sources = await rag.retrieve("kb-test", "query", top_k=5, db=db)

    ids = [s["chunk_id"] for s in sources]
    assert active_id in ids
    assert inactive_id not in ids


@pytest.mark.asyncio
async def test_retrieve_skips_low_score_vector_hits():
    rag = RAGService()
    chunk_id = "low-score-chunk"

    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "ids": [[chunk_id]],
        "documents": [["low"]],
        "distances": [[0.95]],
        "metadatas": [[{"chunk_index": 0, "document_id": "d1"}]],
    }

    class _Row:
        id = chunk_id
        is_active = True

    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter([_Row()])

    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=mock_result)
    db.get = AsyncMock(return_value=None)
    db.commit = AsyncMock()

    with (
        patch.object(rag.embedding_service, "embed_query", return_value=[0.0] * 256),
        patch("app.services.rag_service.get_collection", return_value=mock_collection),
    ):
        sources = await rag.retrieve("kb-test", "q", top_k=5, db=db)

    assert sources == []
