"""Cross-Encoder 二阶段重排（Week 1 C1）。

职责：
    在 Hybrid RRF 候选池上用 Cross-Encoder 对 (query, chunk) 打分重排；
    模型加载失败时自动降级为词项 overlap rerank。

依赖：
    sentence-transformers（可选）；未安装或未启用时使用 rerank_service 降级。
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any

from ..core.config import settings
from .rerank_service import rerank_candidates

logger = logging.getLogger(__name__)

_cross_encoder = None
_load_failed = False


def _sigmoid(x: float) -> float:
    """将 reranker 原始 logit 映射到 (0, 1) 便于阈值过滤。"""
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def normalize_rerank_score(raw: float) -> float:
    """Cross-Encoder 分数归一化（0~1）。"""
    if 0.0 <= raw <= 1.0:
        return raw
    return _sigmoid(raw)


def _get_cross_encoder():
    """懒加载 Cross-Encoder 单例。"""
    global _cross_encoder, _load_failed
    if _load_failed:
        return None
    if _cross_encoder is not None:
        return _cross_encoder
    if not getattr(settings, "CROSS_ENCODER_RERANK_ENABLED", False):
        return None
    try:
        from sentence_transformers import CrossEncoder

        model_name = getattr(
            settings,
            "CROSS_ENCODER_MODEL",
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
        )
        device = getattr(settings, "CROSS_ENCODER_DEVICE", "cpu")
        _cross_encoder = CrossEncoder(model_name, max_length=512, device=device)
        logger.info("Cross-Encoder loaded: %s on %s", model_name, device)
        return _cross_encoder
    except Exception as exc:
        _load_failed = True
        logger.warning("Cross-Encoder unavailable, fallback to term rerank: %s", exc)
        return None


def reset_cross_encoder_cache() -> None:
    """测试用：重置模型缓存。"""
    global _cross_encoder, _load_failed
    _cross_encoder = None
    _load_failed = False


def cross_encoder_rerank(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    top_k: int,
) -> list[dict[str, Any]]:
    """Cross-Encoder 重排；失败时降级词项 rerank。"""
    if not candidates:
        return []

    model = _get_cross_encoder()
    if model is None:
        return rerank_candidates(query, candidates, top_k=top_k)

    start = time.perf_counter()
    pairs = [(query, (c.get("content") or "")[:2000]) for c in candidates]
    try:
        raw_scores = model.predict(pairs)
    except Exception as exc:
        logger.warning("Cross-Encoder predict failed, fallback: %s", exc)
        return rerank_candidates(query, candidates, top_k=top_k)

    for c, raw in zip(candidates, raw_scores, strict=True):
        rs = float(raw)
        c["cross_encoder_raw"] = round(rs, 6)
        c["cross_encoder_score"] = round(normalize_rerank_score(rs), 6)
        c["rerank_score"] = c["cross_encoder_score"]
        c["score"] = c["cross_encoder_score"]

    ranked = sorted(candidates, key=lambda x: x.get("cross_encoder_score", 0), reverse=True)
    elapsed_ms = (time.perf_counter() - start) * 1000
    for c in ranked[:top_k]:
        c["rerank_ms"] = round(elapsed_ms, 2)
    return ranked[:top_k]
