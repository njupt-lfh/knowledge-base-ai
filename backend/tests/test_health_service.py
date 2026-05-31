from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.health_service import knowledge_base_health


@pytest.mark.asyncio
async def test_knowledge_base_health_healthy():
    db = MagicMock()
    kb_row = MagicMock()
    kb_row.id = "kb-test"
    db.get = AsyncMock(return_value=kb_row)
    with patch(
        "app.services.health_service.cold_knowledge_count",
        AsyncMock(return_value={"cold_count_90d": 0, "cold_count_total": 0, "threshold_days": 90}),
    ):
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar=lambda: 0),
                MagicMock(scalar=lambda: 0),
                MagicMock(scalar=lambda: 0),
                MagicMock(scalar=lambda: 10),
                MagicMock(scalar=lambda: 8),
            ]
        )
        result = await knowledge_base_health(db, "kb-test")
    assert result["level"] == "healthy"
    assert result["attention_score"] == 0
