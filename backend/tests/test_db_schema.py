"""数据库 schema 初始化单元测试。

验证内容：
  - init_db 创建全部 ORM 表
  - 关键 Phase 1 表名在 expected_table_names 中

运行方式（在 backend 目录）:
  pytest tests/test_db_schema.py -v

预期结果：全部用例通过，无 missing tables。
"""

import pytest
from app.core.database import expected_table_names, init_db, verify_schema


@pytest.mark.asyncio
async def test_init_db_creates_all_orm_tables():
    """init_db 后 verify_schema 应返回空列表，且包含 Phase 1 核心表。"""
    await init_db()
    missing = await verify_schema()
    assert missing == [], f"missing tables: {missing}"

    expected = expected_table_names()
    assert "chunk_feedback" in expected
    assert "chunk_quality" in expected
    assert "knowledge_gaps" in expected
    assert "knowledge_conflicts" in expected
    assert "answer_review_queue" in expected
    assert "governance_suggestions" in expected
    assert "governance_audit_log" in expected
    assert "gap_audit_log" in expected
