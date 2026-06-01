"""RAG 评测子包入口。

聚合导出检索指标计算、DeepEval 运行与门禁检查函数，
供 `api/eval.py` 与 `scripts/run_rag_eval.py` 等评测流水线调用。
"""

from .deepeval_runner import (
    check_deepeval_gates,
    check_knowledge_retention,
    run_deepeval,
)
from .retrieval_metrics import retrieval_metrics

__all__ = [
    "retrieval_metrics",
    "run_deepeval",
    "check_deepeval_gates",
    "check_knowledge_retention",
]
