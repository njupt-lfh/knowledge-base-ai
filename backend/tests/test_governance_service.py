from app.services.governance_service import (
    ACTION_ARCHIVE,
    DUPLICATE_MAX_DISTANCE,
    _suggestion,
)


def test_suggestion_shape():
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
    assert DUPLICATE_MAX_DISTANCE == 0.4
