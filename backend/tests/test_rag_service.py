"""RAGService 检索路径单元测试。

验证内容：
  - Hybrid 检索命中 chunk 并返回
  - 无 db 或 Hybrid 空结果时返回空列表

运行方式（在 backend 目录）:
  pytest tests/test_rag_service.py -v

预期结果：全部用例通过。
"""

from unittest.mock import AsyncMock, patch

import pytest
from app.models.chunk import Chunk
from app.services.rag_service import RAGService
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_retrieve_hybrid_path():
    """mock Hybrid.search 返回命中时，retrieve 应返回对应 chunk。"""
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
        """fake_search 函数。"""
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
    """未传入 db 时应直接返回空列表。"""
    rag = RAGService()
    sources = await rag.retrieve("kb-test", "q", top_k=5, db=None)
    assert sources == []


@pytest.mark.asyncio
async def test_retrieve_returns_empty_when_hybrid_empty():
    """Hybrid 无命中时应返回空列表。"""
    rag = RAGService()
    db = AsyncMock(spec=AsyncSession)
    with patch.object(rag.hybrid, "search", AsyncMock(return_value=[])):
        sources = await rag.retrieve("kb-test", "q", top_k=5, db=db)
    assert sources == []
