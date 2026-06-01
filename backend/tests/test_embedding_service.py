"""EmbeddingService 单元测试。

验证内容：
  - mock 模式下 embed_query 确定性输出
  - embed_documents 批量向量化维度正确

运行方式（在 backend 目录）:
  pytest tests/test_embedding_service.py -v

预期结果：全部用例通过。
"""

from app.services.embedding_service import EmbeddingService


def test_embed_query_mock_deterministic():
    """相同 query 应返回相同向量，不同 query 应不同；维度为 256。"""
    svc = EmbeddingService()
    assert svc.mock_mode is True
    a = svc.embed_query("test-query")
    b = svc.embed_query("test-query")
    c = svc.embed_query("other")
    assert len(a) == 256
    assert a == b
    assert a != c


def test_embed_documents_batch():
    """批量 embed 应返回与输入等长的向量列表，每条维度 256。"""
    svc = EmbeddingService()
    vecs = svc.embed_documents(["a", "b"])
    assert len(vecs) == 2
    assert all(len(v) == 256 for v in vecs)
