"""Week 2 query router 与 v2 数据集构建测试。"""

from app.eval.dataset_builder_v2 import (
    BANNED_PHRASES,
    _extract_term,
    _has_banned_phrase,
)
from app.services.query_router import route_query


def test_multi_hop_eval_question_routes_relational():
    q = "综合两段内容，「Python 异步」与「React 18」有何关联？"
    assert route_query(q) == "relational"


def test_kg_style_multi_hop_routes_relational():
    q = "「Python」和「asyncio」之间有什么联系？（通过使用）"
    assert route_query(q) == "relational"


def test_v2_natural_fact_no_banned_phrase():
    term = _extract_term("Python 是一门高级编程语言，广泛用于 AI。")
    question = f"{term}是什么？"
    assert not _has_banned_phrase(question)
    assert not any(p in question for p in BANNED_PHRASES)
