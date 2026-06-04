"""Phase 1 P1：near_domain gate、aggregate 分项、compare_eval_runs 单测。"""

from unittest.mock import patch

import pytest

from app.eval.aggregate import aggregate_by_negative_subtype
from app.services.retrieval_gate import apply_retrieval_abstention

# compare_eval_runs 在 scripts/ 下，按 run_rag_eval 同款路径导入
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from scripts.compare_eval_runs import compare_reports, format_comparison  # noqa: E402


def _settings_patch(**overrides):
    """构造 retrieval_gate settings mock。"""
    from contextlib import contextmanager

    defaults = {
        "RETRIEVAL_ABSTAIN_ENABLED": True,
        "CROSS_ENCODER_RERANK_ENABLED": True,
        "NEAR_DOMAIN_GATE_ENABLED": True,
        "NEAR_DOMAIN_CE_MAX": 0.45,
        "RETRIEVAL_ABSTAIN_MIN_SCORE": 0.06,
        "RETRIEVAL_ABSTAIN_MIN_OVERLAP": 0.12,
        "RETRIEVAL_ABSTAIN_MIN_SUBSTANTIVE": 0.05,
        "RETRIEVAL_ABSTAIN_MIN_ANCHOR": 0.20,
        "RETRIEVAL_ABSTAIN_MIN_ANCHOR_MATCHES": 2,
    }
    defaults.update(overrides)

    @contextmanager
    def _cm():
        with patch("app.services.retrieval_gate.settings") as s:
            for k, v in defaults.items():
                setattr(s, k, v)
            yield s

    return _cm()


def test_near_domain_ce_band_anchor_mismatch_abstains():
    """CE ∈ [0.35, 0.45) 且 anchor 不匹配 → 空检索。"""
    query = "本知识库中「Python 异步编程」章节的详细说明是什么？"
    sources = [
        {
            "chunk_id": "a",
            "content": "Java 同步 IO 模型与线程池调度",
            "score": 0.12,
            "cross_encoder_score": 0.40,
        }
    ]
    with _settings_patch():
        out = apply_retrieval_abstention(query, sources, "factual")
    assert out == []


def test_near_domain_ce_band_anchor_match_keeps():
    """CE ∈ [0.35, 0.45) 但 anchor 命中充分 → 保留。"""
    query = "本知识库中「Python 异步编程」章节的详细说明是什么？"
    sources = [
        {
            "chunk_id": "a",
            "content": "Python 异步编程章节 asyncio await 协程详细说明",
            "score": 0.12,
            "cross_encoder_score": 0.40,
        }
    ]
    with _settings_patch():
        out = apply_retrieval_abstention(query, sources, "factual")
    assert len(out) == 1


def test_near_domain_disabled_skips_gate():
    """NEAR_DOMAIN_GATE_ENABLED=false 时不触发 near_domain 规则。"""
    query = "本知识库中「Python 异步编程」章节的详细说明是什么？"
    sources = [
        {
            "chunk_id": "a",
            "content": "Java 同步 IO",
            "score": 0.12,
            "cross_encoder_score": 0.40,
        }
    ]
    with _settings_patch(NEAR_DOMAIN_GATE_ENABLED=False):
        out = apply_retrieval_abstention(query, sources, "factual")
    assert isinstance(out, list)


def test_aggregate_by_negative_subtype():
    """负例子类型分项聚合。"""
    samples = [
        {"q_type": "negative", "negative_subtype": "near_domain", "negative_ok": True},
        {"q_type": "negative", "negative_subtype": "near_domain", "negative_ok": False},
        {"q_type": "negative", "negative_subtype": "unrelated", "negative_ok": True},
        {"q_type": "fact", "negative_ok": None},
    ]
    out = aggregate_by_negative_subtype(samples)
    assert set(out.keys()) == {"near_domain", "unrelated"}
    assert out["near_domain"]["sample_count"] == 2
    assert out["near_domain"]["negative_reject_rate"] == 0.5
    assert out["unrelated"]["negative_reject_rate"] == 1.0


def test_compare_eval_runs_delta():
    """compare_reports 计算指标 delta。"""
    before = {
        "dataset_version": "v1",
        "generated_at": "2026-01-01",
        "aggregate": {
            "context_recall_mean": 0.90,
            "negative_reject_rate": 0.80,
            "sample_count": 100,
        },
        "by_negative_subtype": {
            "near_domain": {"negative_reject_rate": 0.75, "sample_count": 20},
        },
    }
    after = {
        "dataset_version": "v1",
        "generated_at": "2026-06-01",
        "aggregate": {
            "context_recall_mean": 0.91,
            "negative_reject_rate": 1.0,
            "sample_count": 100,
        },
        "by_negative_subtype": {
            "near_domain": {"negative_reject_rate": 1.0, "sample_count": 20},
        },
    }
    comp = compare_reports(before, after)
    assert comp["metrics"]["context_recall_mean"]["delta"] == pytest.approx(0.01)
    assert comp["metrics"]["negative_reject_rate"]["delta"] == pytest.approx(0.2)
    assert comp["by_negative_subtype"]["near_domain"]["negative_reject_rate"]["delta"] == pytest.approx(0.25)
    text = format_comparison(comp)
    assert "negative_reject_rate" in text
    assert "near_domain" in text


def test_run_rag_eval_versioned_paths():
    """run_rag_eval 分文件路径 helper。"""
    from scripts.run_rag_eval import REPORT_FILE_V1, REPORT_FILE_V2, _versioned_report_path

    assert _versioned_report_path("v1") == REPORT_FILE_V1
    assert _versioned_report_path("v2") == REPORT_FILE_V2
