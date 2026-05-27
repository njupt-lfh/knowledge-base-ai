from app.services.hybrid_retriever import dynamic_top_k, reciprocal_rank_fusion


def test_rrf_merged_rank():
    scores = reciprocal_rank_fusion([["a", "b", "c"], ["b", "d"]])
    assert scores["b"] > scores["a"]
    assert scores["b"] > scores["d"]


def test_dynamic_top_k():
    assert dynamic_top_k("短问") <= 5
    assert dynamic_top_k("x" * 100) >= 5
