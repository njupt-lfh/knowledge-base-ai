"""检索 abstention gate 测试"""

from app.services.retrieval_gate import apply_retrieval_abstention


def test_abstain_low_confidence():
    sources = [{"chunk_id": "a", "content": "无关内容", "score": 0.05}]
    out = apply_retrieval_abstention("量子纠缠实验步骤", sources, "factual", graph_paths=[])
    assert out == []


def test_keep_graph_backed():
    sources = [{"chunk_id": "a", "content": "Python和Java", "score": 0.12, "source": "graph"}]
    paths = [{"subject": "Python", "predicate": "对比", "object": "Java", "chunk_id": "a"}]
    out = apply_retrieval_abstention("Python和Java区别", sources, "relational", graph_paths=paths)
    assert len(out) == 1


def test_keep_high_overlap():
    sources = [{"chunk_id": "a", "content": "React 18 Suspense 源码分析章节详解", "score": 0.25}]
    out = apply_retrieval_abstention("React 18 Suspense 源码分析", sources, "factual", graph_paths=[])
    assert len(out) == 1
