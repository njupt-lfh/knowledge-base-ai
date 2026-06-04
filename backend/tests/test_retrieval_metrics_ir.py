"""标准 IR 指标单元测试。"""

from app.eval.retrieval_metrics import (
    compute_mrr,
    compute_ndcg,
    compute_precision_at_k,
    retrieval_metrics,
)


def test_mrr_first_rank():
    assert compute_mrr(["a", "b"], {"a"}) == 1.0


def test_mrr_second_rank():
    assert compute_mrr(["x", "a"], {"a"}) == 0.5


def test_precision_at_k():
    assert compute_precision_at_k(["a", "b", "x"], {"a", "b"}, 3) == round(2 / 3, 4)


def test_ndcg_perfect():
    assert compute_ndcg(["a", "b"], {"a", "b"}, k=2) == 1.0


def test_retrieval_metrics_includes_ir_fields():
    m = retrieval_metrics({"a"}, ["a", "x"], "fact")
    assert m["mrr"] == 1.0
    assert m["precision_at_1"] == 1.0
    assert m["context_precision_chunk"] == m["context_precision"]
