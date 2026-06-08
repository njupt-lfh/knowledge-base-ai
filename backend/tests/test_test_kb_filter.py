"""测试知识库识别与列表过滤。"""

import uuid

import pytest
from app.core.database import async_session, init_db
from app.models.knowledge_base import KnowledgeBase
from app.services.knowledge_service import KnowledgeService
from app.utils.test_kb import is_test_knowledge_base, production_kb_clause


def test_is_test_knowledge_base_by_id_prefix():
    assert is_test_knowledge_base("kb-sync-api-abc", "sync-api") is True
    assert is_test_knowledge_base("kb-t4-deadbeef", "t") is True
    assert is_test_knowledge_base("d189f251-08c4-4e18-8d3d-0e9639b7f6ff", "理财消费") is False


def test_is_test_knowledge_base_by_name_fallback():
    assert is_test_knowledge_base("legacy-id", "fts-test") is True
    assert is_test_knowledge_base("legacy-id", "conflict-kb-abc") is True


def test_production_kb_clause_excludes_kb_prefix():
    clause = production_kb_clause(KnowledgeBase)
    compiled = str(clause.compile(compile_kwargs={"literal_binds": True}))
    assert "kb-" in compiled


@pytest.mark.asyncio
async def test_knowledge_list_excludes_test_kb():
    await init_db()
    suffix = uuid.uuid4().hex[:8]
    test_id = f"kb-list-filter-{suffix}"
    prod_id = f"prod-list-{suffix}"

    async with async_session() as db:
        db.add(KnowledgeBase(id=test_id, name="t"))
        db.add(KnowledgeBase(id=prod_id, name=f"正式库-{suffix}"))
        await db.commit()

        svc = KnowledgeService(db)
        items, total = await svc.list(page=1, page_size=50, search=None)
        ids = {i.id for i in items}
        assert test_id not in ids
        assert prod_id in ids
        assert total >= 1
