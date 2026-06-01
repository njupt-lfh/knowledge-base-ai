"""RAGService 上下文压缩单元测试。

验证内容：
  - compress_context 在 max_chars 预算内截断并保留来源标记

运行方式（在 backend 目录）:
  pytest tests/test_rag_context.py -v

预期结果：全部用例通过。
"""

from app.services.rag_service import RAGService


def test_compress_context_budget():
    """5 条长来源压缩后总字符数不超过预算，且含 [来源 1] 标记。"""
    sources = [{"content": "x" * 2000} for _ in range(5)]
    out = RAGService.compress_context(sources, max_chars=3000)
    assert len(out) <= 3100
    assert "[来源 1]" in out
