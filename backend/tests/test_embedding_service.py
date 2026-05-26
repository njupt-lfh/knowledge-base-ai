from app.services.embedding_service import EmbeddingService


def test_embed_query_mock_deterministic():
    svc = EmbeddingService()
    assert svc.mock_mode is True
    a = svc.embed_query("test-query")
    b = svc.embed_query("test-query")
    c = svc.embed_query("other")
    assert len(a) == 256
    assert a == b
    assert a != c


def test_embed_documents_batch():
    svc = EmbeddingService()
    vecs = svc.embed_documents(["a", "b"])
    assert len(vecs) == 2
    assert all(len(v) == 256 for v in vecs)
