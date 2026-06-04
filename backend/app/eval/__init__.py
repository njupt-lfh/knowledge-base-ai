"""RAG 评测子包入口。

聚合导出检索指标计算、DeepEval 运行与门禁检查函数，
供 `api/eval.py` 与 `scripts/run_rag_eval.py` 等评测流水线调用。
"""

from .aggregate import aggregate_by_key, aggregate_sample_metrics, merge_ragas_into_aggregate
from .deepeval_runner import (
    check_deepeval_gates,
    check_knowledge_retention,
    run_deepeval,
)
from .retrieval_metrics import (
    compute_mrr,
    compute_ndcg,
    compute_precision_at_k,
    retrieval_metrics,
)

__all__ = [
    "aggregate_by_key",
    "aggregate_sample_metrics",
    "merge_ragas_into_aggregate",
    "retrieval_metrics",
    "compute_mrr",
    "compute_ndcg",
    "compute_precision_at_k",
    "run_deepeval",
    "check_deepeval_gates",
    "check_knowledge_retention",
]
