from app.services.rag_service import RAGService


def test_compress_context_budget():
    sources = [{"content": "x" * 2000} for _ in range(5)]
    out = RAGService.compress_context(sources, max_chars=3000)
    assert len(out) <= 3100
    assert "[来源 1]" in out
