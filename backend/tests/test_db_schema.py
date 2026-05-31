import pytest
from app.core.database import expected_table_names, init_db, verify_schema


@pytest.mark.asyncio
async def test_init_db_creates_all_orm_tables():
    await init_db()
    missing = await verify_schema()
    assert missing == [], f"missing tables: {missing}"

    expected = expected_table_names()
    assert "chunk_feedback" in expected
    assert "chunk_quality" in expected
    assert "knowledge_gaps" in expected
    assert "knowledge_conflicts" in expected
