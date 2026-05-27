"""DeepEval 评测单元测试 — Phase 2.4（offline 代理指标 + 回归门禁）"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.eval.deepeval_runner import (
    check_deepeval_gates,
    check_knowledge_retention,
    offline_contextual_relevancy,
    offline_hallucination_score,
    run_deepeval,
    run_deepeval_offline,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "eval_smoke_samples.json"


@pytest.fixture
def smoke_rows():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_offline_contextual_relevancy():
    score = offline_contextual_relevancy(
        "向量数据库 embedding 检索",
        ["Chroma 存储 chunk embedding 做语义检索"],
    )
    assert score >= 0.3


def test_offline_hallucination_score():
    score = offline_hallucination_score(
        "RAG 检索增强生成",
        ["RAG 是 Retrieval Augmented Generation 检索增强生成"],
    )
    assert score >= 0.4


def test_run_deepeval_offline_smoke(smoke_rows):
    out = run_deepeval_offline(smoke_rows)
    assert out["mode"] == "offline"
    assert out["hallucination_mean"] is not None
    assert out["contextual_relevancy_mean"] is not None
    assert out["sample_count"] >= 2


def test_deepeval_gates_pass(smoke_rows):
    scores = run_deepeval_offline(smoke_rows)
    gates = check_deepeval_gates(scores)
    assert gates["passed"] is True


def test_knowledge_retention_pass():
    r = check_knowledge_retention(
        {"context_recall_mean": 0.81, "context_precision_mean": 0.27},
        {"context_recall_mean": 0.75, "context_precision_mean": 0.25},
    )
    assert r["passed"] is True


def test_knowledge_retention_fail_on_recall_drop():
    r = check_knowledge_retention(
        {"context_recall_mean": 0.81},
        {"context_recall_mean": 0.40},
    )
    assert r["passed"] is False


def test_run_deepeval_prefers_offline_in_mock_mode(smoke_rows):
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.LLM_MOCK_MODE = True
        mock_settings.VOLCENGINE_API_KEY = "key"
        out = run_deepeval(smoke_rows, prefer_live=True)
    assert out["mode"] == "offline"


def test_build_llm_test_cases_skips_negative(smoke_rows):
    from app.eval.deepeval_runner import build_llm_test_cases

    cases = build_llm_test_cases(smoke_rows)
    assert len(cases) == 3
    assert all("火星" not in c.input for c in cases)


def test_run_deepeval_live_mocked(smoke_rows):
    from app.eval.deepeval_runner import run_deepeval_live

    fake_metric = MagicMock()
    fake_metric.score = 0.9

    with patch("app.eval.deepeval_runner.VolcengineDeepEvalLLM") as mock_llm:
        mock_llm.return_value.model = MagicMock()
        with patch("deepeval.metrics.HallucinationMetric", return_value=fake_metric):
            with patch("deepeval.metrics.ContextualRelevancyMetric", return_value=fake_metric):
                out = run_deepeval_live(smoke_rows)
    assert out["mode"] == "live"
    assert out["hallucination_mean"] == 0.9
