"""QualityService 质量分计算单元测试。

验证内容：
  - compute_quality_score 输出区间
  - dislike 降低分数、blend_retrieval_score 加权
  - 旧 chunk 新鲜度衰减

运行方式（在 backend 目录）:
  pytest tests/test_quality_service.py -v

预期结果：全部用例通过。
"""

from datetime import datetime, timedelta

from app.services.quality_service import (
    blend_retrieval_score,
    compute_quality_score,
)


def test_compute_quality_score_range():
    """正常输入下质量分应在 [0, 1]。"""
    score = compute_quality_score(
        hit_count=10,
        like_count=5,
        dislike_count=1,
        correction_count=0,
        created_at=datetime.utcnow(),
    )
    assert 0.0 <= score <= 1.0


def test_dislike_lowers_score():
    """相同 hit 下 dislike 多应使分数低于 like 多。"""
    good = compute_quality_score(
        hit_count=5,
        like_count=10,
        dislike_count=0,
        correction_count=0,
        created_at=datetime.utcnow(),
    )
    bad = compute_quality_score(
        hit_count=5,
        like_count=0,
        dislike_count=10,
        correction_count=0,
        created_at=datetime.utcnow(),
    )
    assert bad < good


def test_blend_retrieval_score():
    """检索分与质量分按 0.7/0.3 加权混合。"""
    blended = blend_retrieval_score(0.8, 0.2)
    assert blended == round(0.7 * 0.8 + 0.3 * 0.2, 4)


def test_freshness_decay():
    """400 天前的 chunk 新鲜度应低于刚创建的。"""
    old = compute_quality_score(
        hit_count=5,
        like_count=2,
        dislike_count=0,
        correction_count=0,
        created_at=datetime.utcnow() - timedelta(days=400),
    )
    fresh = compute_quality_score(
        hit_count=5,
        like_count=2,
        dislike_count=0,
        correction_count=0,
        created_at=datetime.utcnow(),
    )
    assert fresh >= old
