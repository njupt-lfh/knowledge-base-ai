"""GovernanceService 建议结构单元测试。

验证内容：
  - _suggestion 返回字段完整
  - DUPLICATE_MAX_DISTANCE 阈值常量

运行方式（在 backend 目录）:
  pytest tests/test_governance_service.py -v

预期结果：全部用例通过。
"""

from app.services.governance_service import (
    ACTION_ARCHIVE,
    DUPLICATE_MAX_DISTANCE,
    _suggestion,
)


def test_suggestion_shape():
    """治理建议 dict 应包含 type、recommended_action、chunk_ids 与 id 前缀。"""
    row = _suggestion(
        stype="cold_stale",
        title="t",
        description="d",
        chunk_ids=["c1"],
        action=ACTION_ARCHIVE,
        severity="warning",
        preview="preview",
    )
    assert row["type"] == "cold_stale"
    assert row["recommended_action"] == ACTION_ARCHIVE
    assert row["chunk_ids"] == ["c1"]
    assert row["id"].startswith("cold_stale:")


def test_duplicate_distance_threshold():
    """重复检测 Chroma 距离上限应为 0.4。"""
    assert DUPLICATE_MAX_DISTANCE == 0.4
