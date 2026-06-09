"""quality_gate 硬过滤单元测试（Phase 1 P1-5）。"""

from app.services.quality_service import apply_quality_gate


def test_passes_normal_candidate():
    """正常候选应通过。"""
    c = [{"chunk_id": "a"}]
    r = apply_quality_gate(c, quality_scores={"a": 0.6})
    assert len(r) == 1


def test_blocks_low_quality():
    """低于阈值的应被过滤。"""
    c = [{"chunk_id": "a"}]
    r = apply_quality_gate(c, quality_scores={"a": 0.19})
    assert len(r) == 0


def test_passes_cold_start_baseline():
    """零命中冷启动分块（~0.247）应通过门控。"""
    c = [{"chunk_id": "a"}]
    r = apply_quality_gate(c, quality_scores={"a": 0.247})
    assert len(r) == 1


def test_blocks_blacklist_dislike():
    """dislike>=3 应进黑名单。"""
    c = [{"chunk_id": "a"}]
    r = apply_quality_gate(
        c,
        quality_scores={"a": 0.6},
        quality_details={"a": {"dislike_count": 3, "needs_review": False}},
    )
    assert len(r) == 0


def test_blocks_needs_review_dislike():
    """needs_review 且 dislike>=2 应过滤。"""
    c = [{"chunk_id": "a"}]
    r = apply_quality_gate(
        c,
        quality_scores={"a": 0.6},
        quality_details={"a": {"dislike_count": 2, "needs_review": True}},
    )
    assert len(r) == 0


def test_passes_needs_review_low_dislike():
    """needs_review 但 dislike<2 应放行（质量分合格时）。"""
    c = [{"chunk_id": "a"}]
    r = apply_quality_gate(
        c,
        quality_scores={"a": 0.6},
        quality_details={"a": {"dislike_count": 1, "needs_review": True}},
    )
    assert len(r) == 1


def test_new_chunk_default_passes():
    """新 chunk（无 quality 记录）默认 0.5 应通过。"""
    c = [{"chunk_id": "new"}]
    r = apply_quality_gate(c, quality_scores={})  # not in map → default 0.5
    assert len(r) == 1


def test_empty_candidates():
    """空列表应返回空。"""
    assert apply_quality_gate([], quality_scores={}) == []
