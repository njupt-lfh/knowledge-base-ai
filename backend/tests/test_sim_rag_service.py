"""SIM-RAG — Phase 4.3"""

from app.services.sim_rag_service import (
    decompose_sub_queries,
    evaluate_subquery_coverage,
    should_use_sim_rag,
)


def test_decompose_multi_question():
    qs = decompose_sub_queries("RAG是什么？向量检索如何工作？")
    assert len(qs) >= 2


def test_should_use_sim_rag_comprehensive():
    assert should_use_sim_rag("comprehensive", "请总结知识库中有哪些模块")


def test_subquery_coverage():
    sources = [{"content": "vector search uses embedding store"}]
    cov = evaluate_subquery_coverage(["vector search"], sources)
    assert cov == 1.0
