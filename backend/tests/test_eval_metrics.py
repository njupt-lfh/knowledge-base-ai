from app.eval.retrieval_metrics import retrieval_metrics


def test_positive_full_recall():
    m = retrieval_metrics({"a", "b"}, ["a", "b", "x"], "fact")
    assert m["context_recall"] == 1.0
    assert m["retrieval_hit"] is True


def test_partial_recall():
    m = retrieval_metrics({"a", "b"}, ["a"], "fact")
    assert m["context_recall"] == 0.5
    assert m["retrieval_hit"] is True


def test_negative_empty_retrieval_ok():
    m = retrieval_metrics(set(), [], "negative")
    assert m["negative_ok"] is True
    assert m["context_recall"] == 1.0


def test_negative_with_retrieval_fails():
    m = retrieval_metrics(set(), ["noise"], "negative")
    assert m["negative_ok"] is False
