"""DeepEval 评测运行器（Phase 2.4）。

提供 Hallucination、Contextual Relevancy 的 offline/live 评测，
Volcengine Judge 适配，以及 CI 门禁与 Knowledge Retention 回归检查。
"""

from __future__ import annotations

import logging
import re
from statistics import mean
from typing import Any

logger = logging.getLogger(__name__)


def _terms(text: str) -> set[str]:
    """从文本提取词项集合（英文单词与中文连续字符，长度≥2）。"""
    return set(re.findall(r"[\w\u4e00-\u9fff]{2,}", (text or "").lower()))


def offline_contextual_relevancy(question: str, contexts: list[str]) -> float:
    """检索上下文与问题的词项重叠度（0–1，越高越相关）。

    参数:
        question: 用户问题文本。
        contexts: 检索到的上下文片段列表。

    返回:
        各上下文与问题词项重叠比例的最大值，保留四位小数。
    """
    q_terms = _terms(question)
    if not q_terms or not contexts:
        return 0.0
    overlaps: list[float] = []
    for ctx in contexts:
        c_terms = _terms(ctx)
        if c_terms:
            overlaps.append(len(q_terms & c_terms) / len(q_terms))
    return round(max(overlaps) if overlaps else 0.0, 4)


def offline_hallucination_score(answer: str, contexts: list[str]) -> float:
    """回答词项被上下文覆盖的比例（越高表示越忠实、越少幻觉）。

    参数:
        answer: 模型生成的回答。
        contexts: 参考上下文列表。

    返回:
        回答词项在上下文并集中的覆盖比例，上限 1.0。
    """
    a_terms = _terms(answer)
    if not a_terms:
        return 1.0
    ctx_terms: set[str] = set()
    for ctx in contexts:
        ctx_terms |= _terms(ctx)
    if not ctx_terms:
        return 0.0
    covered = len(a_terms & ctx_terms) / len(a_terms)
    return round(min(1.0, covered), 4)


def build_llm_test_cases(rows: list[dict]) -> list[Any]:
    """将评测行转换为 DeepEval LLMTestCase 列表。

    参数:
        rows: 含 question/answer/contexts/ground_truth/q_type 的字典列表。

    返回:
        跳过负样本与无上下文样本后的 LLMTestCase 列表。
    """
    from deepeval.test_case import LLMTestCase

    cases: list[LLMTestCase] = []
    for r in rows:
        if r.get("q_type") == "negative" or not r.get("answer"):
            continue
        ctx = [c for c in (r.get("contexts") or []) if c]
        if not ctx:
            continue
        cases.append(
            LLMTestCase(
                input=r["question"],
                actual_output=r["answer"],
                context=ctx,
                retrieval_context=ctx,
                expected_output=r.get("ground_truth") or "",
            )
        )
    return cases


class VolcengineDeepEvalLLM:
    """DeepEval 自定义 Judge — 复用项目 LLMService（火山引擎豆包）。"""

    def __init__(self) -> None:
        from deepeval.models.base_model import DeepEvalBaseLLM

        from ..core.config import settings
        from ..services.llm_service import LLMService

        class _Impl(DeepEvalBaseLLM):
            def __init__(self) -> None:
                self._svc = LLMService()
                super().__init__(settings.VOLCENGINE_LLM_MODEL)

            def load_model(self, *args, **kwargs):
                return self._svc

            def get_model_name(self, *args, **kwargs) -> str:
                return self.model_name

            def generate(self, prompt: str, *args, **kwargs) -> str:
                import asyncio

                # DeepEval 可能在已有事件循环中同步调用 generate
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    return asyncio.run(self.a_generate(prompt))
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(lambda: asyncio.run(self.a_generate(prompt))).result()

            async def a_generate(self, prompt: str, *args, **kwargs) -> str:
                return await self._svc.chat_completion(
                    [{"role": "user", "content": prompt}],
                    temperature=0,
                    max_tokens=1024,
                )

        self._impl = _Impl()

    @property
    def model(self):
        """返回 DeepEval 兼容的 LLM 实现实例。"""
        return self._impl


def run_deepeval_offline(rows: list[dict]) -> dict[str, Any]:
    """无 API 的确定性代理指标，供 CI 默认门禁。

    参数:
        rows: 评测数据集行。

    返回:
        含 mode、sample_count、hallucination_mean、contextual_relevancy_mean 的结果字典。
    """
    h_scores: list[float] = []
    c_scores: list[float] = []
    for r in rows:
        if r.get("q_type") == "negative":
            continue
        ctx = r.get("contexts") or []
        ans = r.get("answer") or ""
        if not ctx and not ans:
            continue
        if ans and ctx:
            h_scores.append(offline_hallucination_score(ans, ctx))
        if ctx:
            c_scores.append(offline_contextual_relevancy(r.get("question", ""), ctx))

    return {
        "mode": "offline",
        "sample_count": max(len(h_scores), len(c_scores)),
        "hallucination_mean": round(mean(h_scores), 4) if h_scores else None,
        "contextual_relevancy_mean": round(mean(c_scores), 4) if c_scores else None,
        "errors": [],
    }


def run_deepeval_live(rows: list[dict]) -> dict[str, Any]:
    """DeepEval 官方指标 + Volcengine Judge 在线评测。

    参数:
        rows: 评测数据集行。

    返回:
        含 mode、sample_count、各指标均值及 errors 列表的结果字典。
    """
    from deepeval.metrics import ContextualRelevancyMetric, HallucinationMetric

    cases = build_llm_test_cases(rows)
    if not cases:
        return {"mode": "live", "sample_count": 0, "errors": ["no eligible rows"], "scores": {}}

    judge = VolcengineDeepEvalLLM().model
    h_metric = HallucinationMetric(threshold=0.5, model=judge, include_reason=False)
    c_metric = ContextualRelevancyMetric(threshold=0.5, model=judge, include_reason=False)

    h_scores: list[float] = []
    c_scores: list[float] = []
    errors: list[str] = []

    for case in cases:
        try:
            h_metric.measure(case)
            if h_metric.score is not None:
                h_scores.append(float(h_metric.score))
        except Exception as exc:
            errors.append(f"hallucination:{case.input[:40]}:{exc}")
        try:
            c_metric.measure(case)
            if c_metric.score is not None:
                c_scores.append(float(c_metric.score))
        except Exception as exc:
            errors.append(f"contextual_relevancy:{case.input[:40]}:{exc}")

    return {
        "mode": "live",
        "sample_count": len(cases),
        "hallucination_mean": round(mean(h_scores), 4) if h_scores else None,
        "contextual_relevancy_mean": round(mean(c_scores), 4) if c_scores else None,
        "errors": errors,
    }


def run_deepeval(rows: list[dict], *, prefer_live: bool = False) -> dict[str, Any]:
    """运行 DeepEval 评测，优先 live 模式并在失败时回退 offline。

    参数:
        rows: 评测数据集行。
        prefer_live: 为 True 且 API 可用时使用在线 Judge。

    返回:
        offline 或 live 模式的聚合分数字典。
    """
    from ..core.config import settings

    if prefer_live and not settings.LLM_MOCK_MODE and settings.VOLCENGINE_API_KEY:
        try:
            return run_deepeval_live(rows)
        except Exception as exc:
            logger.exception("deepeval live failed, fallback offline")
            out = run_deepeval_offline(rows)
            out["errors"] = [str(exc)]
            return out
    return run_deepeval_offline(rows)


def check_knowledge_retention(
    baseline_agg: dict[str, Any],
    current_agg: dict[str, Any],
    *,
    min_recall_ratio: float = 0.85,
    min_precision_ratio: float = 0.80,
) -> dict[str, Any]:
    """Knowledge Retention 回归：更新后指标不低于基线一定比例。

    Phase 2 出口目标为 recall +15%，此处 CI 门禁为「不低于基线 85%」防回退。

    参数:
        baseline_agg: 基线聚合指标（含 context_recall_mean 等）。
        current_agg: 当前运行聚合指标。
        min_recall_ratio: 召回率相对基线的最低比例。
        min_precision_ratio: 精确率相对基线的最低比例。

    返回:
        含 passed 与 details 逐项检查结果的字典。
    """
    checks: dict[str, Any] = {"passed": True, "details": []}

    def _ratio(key: str, min_ratio: float) -> None:
        base = baseline_agg.get(key)
        cur = current_agg.get(key)
        if base is None or cur is None:
            checks["details"].append({"metric": key, "skipped": True, "reason": "missing value"})
            return
        if base <= 0:
            checks["details"].append({"metric": key, "skipped": True, "reason": "zero baseline"})
            return
        ratio = cur / base
        ok = ratio >= min_ratio
        checks["details"].append(
            {
                "metric": key,
                "baseline": base,
                "current": cur,
                "ratio": round(ratio, 4),
                "min_ratio": min_ratio,
                "passed": ok,
            }
        )
        if not ok:
            checks["passed"] = False

    _ratio("context_recall_mean", min_recall_ratio)
    _ratio("context_precision_mean", min_precision_ratio)
    return checks


def check_deepeval_gates(
    scores: dict[str, Any],
    *,
    min_hallucination: float = 0.35,
    min_contextual_relevancy: float = 0.20,
) -> dict[str, Any]:
    """DeepEval 指标门禁（offline/live 通用）。

    参数:
        scores: run_deepeval 返回的分数字典。
        min_hallucination: 幻觉指标最低均值。
        min_contextual_relevancy: 上下文相关度最低均值。

    返回:
        含 passed、details、mode 的门禁结果。
    """
    passed = True
    details: list[dict[str, Any]] = []

    for key, threshold, label in (
        ("hallucination_mean", min_hallucination, "hallucination"),
        ("contextual_relevancy_mean", min_contextual_relevancy, "contextual_relevancy"),
    ):
        val = scores.get(key)
        if val is None:
            details.append({"metric": label, "skipped": True})
            continue
        ok = val >= threshold
        details.append({"metric": label, "value": val, "threshold": threshold, "passed": ok})
        if not ok:
            passed = False

    return {"passed": passed, "details": details, "mode": scores.get("mode", "unknown")}
