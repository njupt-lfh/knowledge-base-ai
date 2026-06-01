"""检索 abstention gate 单元测试。

验证内容：
  - 低置信度 factual 查询应 abstain（返回空）
  - 图谱支撑或高词面重叠应保留来源

运行方式（在 backend 目录）:
  pytest tests/test_retrieval_gate.py -v

预期结果：全部用例通过。
"""

from app.services.retrieval_gate import apply_retrieval_abstention


def test_abstain_low_confidence():
    """低分且无图谱路径时，应清空检索结果。"""
    sources = [{"chunk_id": "a", "content": "无关内容", "score": 0.02}]
    out = apply_retrieval_abstention("量子纠缠实验步骤", sources, "factual", graph_paths=[])
    assert out == []


def test_keep_graph_backed():
    """图谱来源且有 paths 时，即使分数较低也应保留。"""
    sources = [{"chunk_id": "a", "content": "Python和Java", "score": 0.12, "source": "graph"}]
    paths = [{"subject": "Python", "predicate": "对比", "object": "Java", "chunk_id": "a"}]
    out = apply_retrieval_abstention("Python和Java区别", sources, "relational", graph_paths=paths)
    assert len(out) == 1


def test_keep_high_overlap():
    """query 与 chunk 词面高度重叠时，应保留来源。"""
    sources = [{"chunk_id": "a", "content": "React 18 Suspense 源码分析章节详解", "score": 0.25}]
    out = apply_retrieval_abstention(
        "React 18 Suspense 源码分析", sources, "factual", graph_paths=[]
    )
    assert len(out) == 1
