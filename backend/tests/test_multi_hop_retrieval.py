"""multi_hop 分路检索与引号 FTS 单元测试。"""

from app.services.multi_hop_retrieval_service import (
    _fts_search_variants,
    diagnose_retrieval_hits,
    extract_quote_anchors,
    get_multi_hop_anchors,
    merge_multi_hop_with_quota,
    should_use_multi_hop_split,
)
from app.services.query_router import route_query


def test_extract_quote_anchors():
    q = "综合两段，说明「Python 异步」与「React 18」有何关联？"
    spans = extract_quote_anchors(q)
    assert len(spans) >= 2
    assert any("Python" in s for s in spans)


def test_get_multi_hop_anchors_relation():
    anchors = get_multi_hop_anchors("Python与Java的区别是什么？")
    assert len(anchors) >= 2


def test_get_multi_hop_anchors_kg_template():
    q = "「检索增强」和「生成质量」之间有什么联系？（通过提升）"
    anchors = get_multi_hop_anchors(q)
    assert "检索增强" in anchors[0] or any("检索增强" in a for a in anchors)
    assert any("生成质量" in a for a in anchors)
    assert "之间有什么联系" not in anchors


def test_should_use_multi_hop_split():
    q = "「质量强化学习」和「半监督学习」之间有什么联系？（通过强化学习）"
    assert should_use_multi_hop_split(route_query(q), q)


def test_fts_search_variants_strips_book_title():
    variants = _fts_search_variants("论文《人工智能技术会诱致劳动收入不平等吗》")
    assert any("论文" in v or "技术" in v or "人工智能" in v for v in variants)


def test_merge_multi_hop_with_quota_reserves_each_list():
    list_a = [{"chunk_id": "a", "content": "A", "score": 0.9, "source": "hybrid"}]
    list_b = [{"chunk_id": "b", "content": "B", "score": 0.8, "source": "hybrid"}]
    merged = merge_multi_hop_with_quota(
        [list_a, list_b],
        top_k=3,
        quota_lists=[list_a, list_b],
        min_per_list=1,
    )
    ids = [x["chunk_id"] for x in merged]
    assert "a" in ids and "b" in ids


def test_diagnose_hit_buckets():
    full = diagnose_retrieval_hits({"a", "b"}, ["a", "b", "x"])
    assert full["bucket"] == "full"
    partial = diagnose_retrieval_hits({"a", "b"}, ["a"])
    assert partial["bucket"] == "partial"
    miss = diagnose_retrieval_hits({"a", "b"}, ["x"])
    assert miss["bucket"] == "miss"
