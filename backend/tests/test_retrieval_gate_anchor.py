"""锚点 abstention 单元测试（Week 0 Q0-2）。"""

from app.services.crag_evaluator import _anchor_match_count, _anchor_terms_from_query
from app.services.retrieval_gate import apply_retrieval_abstention


def test_anchor_terms_from_quoted_negative():
    q = "本知识库中关于「量子纠缠实验步骤」的详细记录是什么？"
    anchors = _anchor_terms_from_query(q)
    assert "量子" in anchors or "纠缠" in anchors


def test_abstain_react_false_positive():
    """ReAct 框架误命中 react 单锚点时应 abstain。"""
    q = "请介绍本知识库中 React 18 Suspense 源码分析章节。"
    sources = [{"chunk_id": "a", "content": "ReAct 框架用于 Agent 推理", "score": 0.24}]
    out = apply_retrieval_abstention(q, sources, "factual", graph_paths=[])
    assert out == []


def test_multi_hop_relaxed_keeps_dual_entity_chunks():
    """双路合并：A/B 分属两 chunk 时不应被锚点门控清空。"""
    q = "「检索增强」和「生成质量」之间有什么联系？（通过提升）"
    sources = [
        {"chunk_id": "a", "content": "检索增强用于 RAG 流水线", "score": 0.10},
        {"chunk_id": "b", "content": "生成质量依赖解码与采样", "score": 0.09},
    ]
    strict = apply_retrieval_abstention(q, sources, "relational", graph_paths=[])
    relaxed = apply_retrieval_abstention(
        q,
        sources,
        "relational",
        graph_paths=[{"seed": "x"}],
        multi_hop_relaxed=True,
    )
    assert len(relaxed) == 2
    assert len(strict) <= len(relaxed)


def test_keep_anchor_matches_concept():
    q = "请解释知识库中与「RAG 检索增强生成技术」相关的概念。"
    content = "RAG 检索增强生成技术通过外部知识库增强 LLM 回答质量。"
    sources = [{"chunk_id": "a", "content": content, "score": 0.12}]
    anchors = _anchor_terms_from_query(q)
    assert _anchor_match_count(anchors, sources) >= 2
    out = apply_retrieval_abstention(q, sources, "factual", graph_paths=[])
    assert len(out) == 1
