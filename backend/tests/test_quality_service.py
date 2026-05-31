from datetime import datetime, timedelta

from app.services.quality_service import (
    blend_retrieval_score,
    compute_quality_score,
)


def test_compute_quality_score_range():
    score = compute_quality_score(
        hit_count=10,
        like_count=5,
        dislike_count=1,
        correction_count=0,
        created_at=datetime.utcnow(),
    )
    assert 0.0 <= score <= 1.0


def test_dislike_lowers_score():
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
    blended = blend_retrieval_score(0.8, 0.2)
    assert blended == round(0.7 * 0.8 + 0.3 * 0.2, 4)


def test_freshness_decay():
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
