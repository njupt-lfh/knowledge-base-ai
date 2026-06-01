"""SIM-RAG 子查询分解与覆盖度单元测试 — Phase 4.3。

验证内容：
  - decompose_sub_queries 多问号拆分
  - should_use_sim_rag 综合类 query
  - evaluate_subquery_coverage 词面匹配

运行方式（在 backend 目录）:
  pytest tests/test_sim_rag_service.py -v

预期结果：全部用例通过。
"""

from app.services.sim_rag_service import (
    decompose_sub_queries,
    evaluate_subquery_coverage,
    should_use_sim_rag,
)


def test_decompose_multi_question():
    """含多个问号的 query 应拆成 >= 2 个子查询。"""
    qs = decompose_sub_queries("RAG是什么？向量检索如何工作？")
    assert len(qs) >= 2


def test_should_use_sim_rag_comprehensive():
    """comprehensive 路由且多主题 query 应启用 SIM-RAG。"""
    assert should_use_sim_rag("comprehensive", "请总结知识库中有哪些模块")


def test_subquery_coverage():
    """子查询词面出现在 sources 中时覆盖度应为 1.0。"""
    sources = [{"content": "vector search uses embedding store"}]
    cov = evaluate_subquery_coverage(["vector search"], sources)
    assert cov == 1.0
