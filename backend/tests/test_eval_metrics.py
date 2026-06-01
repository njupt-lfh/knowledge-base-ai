"""检索评测指标 retrieval_metrics 单元测试。

验证内容：
  - 正例全召回、部分召回
  - 负例空检索为 ok，有噪声检索为 fail

运行方式（在 backend 目录）:
  pytest tests/test_eval_metrics.py -v

预期结果：全部用例通过。
"""

from app.eval.retrieval_metrics import retrieval_metrics


def test_positive_full_recall():
    """相关 chunk 全部命中时 recall=1.0 且 retrieval_hit=True。"""
    m = retrieval_metrics({"a", "b"}, ["a", "b", "x"], "fact")
    assert m["context_recall"] == 1.0
    assert m["retrieval_hit"] is True


def test_partial_recall():
    """只命中一半相关 chunk 时 recall=0.5。"""
    m = retrieval_metrics({"a", "b"}, ["a"], "fact")
    assert m["context_recall"] == 0.5
    assert m["retrieval_hit"] is True


def test_negative_empty_retrieval_ok():
    """负例无检索结果时 negative_ok=True。"""
    m = retrieval_metrics(set(), [], "negative")
    assert m["negative_ok"] is True
    assert m["context_recall"] == 1.0


def test_negative_with_retrieval_fails():
    """负例检索到无关 chunk 时 negative_ok=False。"""
    m = retrieval_metrics(set(), ["noise"], "negative")
    assert m["negative_ok"] is False
