"""Post-retrieval 过滤与同文档去重单元测试。"""

from app.services.post_retrieval_filter import apply_post_retrieval_filter


def test_filter_low_cross_encoder_score():
    cands = [
        {"chunk_id": "a", "document_id": "d1", "cross_encoder_score": 0.9},
        {"chunk_id": "b", "document_id": "d2", "cross_encoder_score": 0.1},
    ]
    out = apply_post_retrieval_filter(cands, min_score=0.35, use_cross_encoder_threshold=True)
    assert len(out) == 1
    assert out[0]["chunk_id"] == "a"


def test_dedup_same_document():
    cands = [
        {"chunk_id": "a", "document_id": "d1", "cross_encoder_score": 0.9},
        {"chunk_id": "b", "document_id": "d1", "cross_encoder_score": 0.8},
        {"chunk_id": "c", "document_id": "d1", "cross_encoder_score": 0.7},
    ]
    out = apply_post_retrieval_filter(
        cands, min_score=0.0, max_per_document=2, use_cross_encoder_threshold=False
    )
    assert len(out) == 2
    assert {x["chunk_id"] for x in out} == {"a", "b"}


def test_empty_when_all_below_threshold():
    cands = [{"chunk_id": "a", "cross_encoder_score": 0.1, "document_id": "d1"}]
    out = apply_post_retrieval_filter(cands, min_score=0.35, use_cross_encoder_threshold=True)
    # 软降级：保留重排第一名
    assert len(out) == 1
    assert out[0]["chunk_id"] == "a"
