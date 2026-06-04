"""检索 abstention gate 单元测试。

验证内容：
  - 低置信度 factual 查询应 abstain（返回空）
  - 图谱支撑或高词面重叠应保留来源

运行方式（在 backend 目录）:
  pytest tests/test_retrieval_gate.py -v

预期结果：全部用例通过。
"""

from unittest.mock import patch

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


def test_ce_min_score_strict_rejects_below_035():
    """strict 路径：CE top1 < 0.35 应空检索。"""
    sources = [
        {
            "chunk_id": "a",
            "content": "Python Java 对比",
            "score": 0.2,
            "cross_encoder_score": 0.30,
        }
    ]
    with patch("app.services.retrieval_gate.settings") as s:
        s.RETRIEVAL_ABSTAIN_ENABLED = True
        s.CROSS_ENCODER_RERANK_ENABLED = True
        s.RETRIEVAL_ABSTAIN_MIN_SCORE = 0.06
        s.RETRIEVAL_ABSTAIN_MIN_OVERLAP = 0.12
        s.RETRIEVAL_ABSTAIN_MIN_SUBSTANTIVE = 0.05
        s.RETRIEVAL_ABSTAIN_MIN_ANCHOR = 0.20
        s.RETRIEVAL_ABSTAIN_MIN_ANCHOR_MATCHES = 2
        out = apply_retrieval_abstention(
            "Python 和 Java 区别",
            sources,
            "relational",
            ce_min_score=0.35,
        )
    assert out == []


def test_ce_min_score_relaxed_keeps_between_025_and_035():
    """relaxed 路径：CE 0.30 在 τ=0.25 下可保留（高重叠）。"""
    sources = [
        {
            "chunk_id": "a",
            "content": "Python 与 Java 的核心差异与对比分析详解",
            "score": 0.2,
            "cross_encoder_score": 0.30,
        }
    ]
    with patch("app.services.retrieval_gate.settings") as s:
        s.RETRIEVAL_ABSTAIN_ENABLED = True
        s.CROSS_ENCODER_RERANK_ENABLED = True
        s.RETRIEVAL_ABSTAIN_MIN_SCORE = 0.06
        s.RETRIEVAL_ABSTAIN_MIN_OVERLAP = 0.12
        s.RETRIEVAL_ABSTAIN_MIN_SUBSTANTIVE = 0.05
        s.RETRIEVAL_ABSTAIN_MIN_ANCHOR = 0.20
        s.RETRIEVAL_ABSTAIN_MIN_ANCHOR_MATCHES = 2
        out = apply_retrieval_abstention(
            "Python 和 Java 区别",
            sources,
            "relational",
            ce_min_score=0.25,
        )
    assert len(out) == 1
