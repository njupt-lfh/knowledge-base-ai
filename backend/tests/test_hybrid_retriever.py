"""HybridRetriever RRF 与 dynamic_top_k 单元测试。

验证内容：
  - reciprocal_rank_fusion 合并后 b 排名最高
  - dynamic_top_k 随 query 长度变化

运行方式（在 backend 目录）:
  pytest tests/test_hybrid_retriever.py -v

预期结果：全部用例通过。
"""

from app.services.hybrid_retriever import dynamic_top_k, reciprocal_rank_fusion


def test_rrf_merged_rank():
    """b 同时出现在两个列表中，RRF 得分应高于 a。"""
    scores = reciprocal_rank_fusion([["a", "b", "c"], ["b", "d"]])
    assert scores["b"] > scores["a"]
    assert scores["b"] > scores["d"]


def test_dynamic_top_k():
    """短问 top_k 较小，长问 top_k 较大。"""
    assert dynamic_top_k("短问") <= 5
    assert dynamic_top_k("x" * 100) >= 5
