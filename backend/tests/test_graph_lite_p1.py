"""Graph-Lite G-L1 / G-L2 单元测试（Phase 3 P1-8）。"""

from __future__ import annotations

import networkx as nx
from app.services.graph_store_service import expand_graph_paths
from app.services.query_router import decompose_multi_hop_query


def test_decompose_multi_hop_kg_link_template():
    """v2 kg 问法：「A」和「B」之间有什么联系。"""
    seeds = decompose_multi_hop_query("「W-RAG」和「arXiv预印本」之间有什么联系？（通过文献类型）")
    assert len(seeds) == 2
    assert any("W-RAG" in s for s in seeds)
    assert any("arXiv" in s or "预印本" in s for s in seeds)


def test_decompose_multi_hop_relation_pattern():
    """G-L1：「A 与 B 的区别」应分解出两个 anchor。"""
    seeds = decompose_multi_hop_query("Python与Java的区别是什么？")
    assert len(seeds) == 2
    assert seeds[0] == "Python"
    assert seeds[1].startswith("Java")


def test_decompose_multi_hop_v2_template():
    """G-L1：v2 multi_hop 模板「综合两段…「A」与「B」有何关联」。"""
    q = "综合两段内容，「Python 异步编程」与「React 18 并发」有何关联？"
    seeds = decompose_multi_hop_query(q)
    assert len(seeds) >= 2
    assert any("Python" in s for s in seeds)
    assert any("React" in s for s in seeds)


def test_decompose_multi_hop_cjk_fallback():
    """G-L1：无显式 A/B 模式时回退 CJK 词抽取。"""
    seeds = decompose_multi_hop_query("深度学习框架性能对比分析")
    assert seeds
    assert all(len(s) >= 2 for s in seeds)


def test_decompose_multi_hop_empty_query():
    """G-L1：空查询返回空列表。"""
    assert decompose_multi_hop_query("") == []
    assert decompose_multi_hop_query("   ") == []


def test_expand_graph_paths_single_seed_no_hard_filter():
    """G-L2：单 seed 时不做 ≥2 anchor 硬过滤。"""
    graph = nx.DiGraph()
    graph.add_edge("A", "X", chunk_id="c1", predicate="关联")

    scores, paths = expand_graph_paths(graph, ["A"], max_hops=2)

    assert "c1" in scores
    assert paths
    assert paths[0]["anchor_hits"] == 1


def test_expand_graph_paths_multi_seed_filters_disconnected_seeds():
    """G-L2：多种子且无跨 seed 路径时，单锚点 chunk 全部被滤除。"""
    graph = nx.DiGraph()
    graph.add_edge("S1", "Mid", chunk_id="c1", predicate="关联")
    graph.add_edge("S2", "Other", chunk_id="c2", predicate="关联")

    scores, paths = expand_graph_paths(graph, ["S1", "S2"], max_hops=2)

    assert scores == {}
    assert paths == []


def test_expand_graph_paths_multi_seed_keeps_bridge_chunk():
    """G-L2：覆盖两个 seed 的桥接边应保留。"""
    graph = nx.DiGraph()
    graph.add_edge("Alpha", "Beta", chunk_id="c_bridge", predicate="关联")

    scores, paths = expand_graph_paths(graph, ["Alpha", "Beta"], max_hops=2)

    assert "c_bridge" in scores
    assert any(p.get("chunk_id") == "c_bridge" and p.get("anchor_hits", 0) >= 2 for p in paths)
