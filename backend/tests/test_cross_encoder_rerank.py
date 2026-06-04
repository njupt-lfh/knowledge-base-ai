"""Cross-Encoder rerank 降级路径测试。"""

from unittest.mock import patch

from app.services.cross_encoder_rerank_service import (
    cross_encoder_rerank,
    normalize_rerank_score,
    reset_cross_encoder_cache,
)


def test_normalize_rerank_score_sigmoid():
    assert normalize_rerank_score(0.5) == 0.5
    assert normalize_rerank_score(5.0) > 0.99


def test_fallback_to_term_rerank_when_disabled():
    reset_cross_encoder_cache()
    cands = [
        {"chunk_id": "a", "content": "Python 异步编程", "rrf_score": 0.05, "score": 0.05},
        {"chunk_id": "b", "content": "无关", "rrf_score": 0.08, "score": 0.08},
    ]
    with patch("app.services.cross_encoder_rerank_service.settings") as mock_settings:
        mock_settings.CROSS_ENCODER_RERANK_ENABLED = False
        out = cross_encoder_rerank("Python 异步", cands, top_k=1)
    assert len(out) == 1
    assert out[0]["chunk_id"] == "a"
