"""治理闭环 E2E 测试（Phase 3 P0-4 + P1-9）。"""

import json
import os
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("LLM_MOCK_MODE", "true")

from app.core.database import async_session, init_db
from app.main import app
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.governance_suggestion import (
    SUGGESTION_STATUSES,
    SUGGESTION_TYPES,
    GovernanceAuditLog,
    GovernanceSuggestion,
)
from app.models.knowledge_base import KnowledgeBase
from app.services.governance_service import GovernanceService


def test_suggestion_types_defined():
    """建议类型常量完整。"""
    assert "duplicate" in SUGGESTION_TYPES
    assert "cold_stale" in SUGGESTION_TYPES
    assert len(SUGGESTION_TYPES) >= 4


def test_suggestion_statuses_defined():
    """状态机状态完整。"""
    assert "pending" in SUGGESTION_STATUSES
    assert "approved" in SUGGESTION_STATUSES
    assert "executed" in SUGGESTION_STATUSES
    assert "verified" in SUGGESTION_STATUSES


def test_models_registered_in_init():
    """ORM 模型已在 __init__.py 注册。"""
    from app.models import GovernanceAuditLog as GAL
    from app.models import GovernanceSuggestion as GS

    assert GS.__tablename__ == "governance_suggestions"
    assert GAL.__tablename__ == "governance_audit_log"


def test_orm_fields_exist():
    """ORM 字段完整性检查。"""
    assert hasattr(GovernanceSuggestion, "kb_id")
    assert hasattr(GovernanceSuggestion, "suggestion_type")
    assert hasattr(GovernanceSuggestion, "status")
    assert hasattr(GovernanceSuggestion, "chunk_ids")
    assert hasattr(GovernanceSuggestion, "recommended_action")
    assert hasattr(GovernanceSuggestion, "approved_by")
    assert hasattr(GovernanceSuggestion, "executed_by")
    assert hasattr(GovernanceAuditLog, "kb_id")
    assert hasattr(GovernanceAuditLog, "action")
    assert hasattr(GovernanceAuditLog, "suggestion_id")


def test_schema_declares_tables():
    """governance_suggestions / governance_audit_log 在 metadata 中。"""
    from app.core.database import Base

    names = set(Base.metadata.tables.keys())
    assert "governance_suggestions" in names
    assert "governance_audit_log" in names


@pytest.fixture
async def kb_with_chunk():
    """创建含活跃 chunk 的测试知识库。"""
    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb-gov-e2e-{suffix}"
    doc_id = f"d-gov-e2e-{suffix}"
    chunk_id = f"c-gov-e2e-{suffix}"

    async with async_session() as db:
        db.add(
            KnowledgeBase(
                id=kb_id,
                name="gov-e2e",
                embedding_model="m",
                chunk_size=500,
                chunk_overlap=50,
            )
        )
        db.add(
            Document(
                id=doc_id,
                knowledge_base_id=kb_id,
                filename="t.txt",
                file_type="txt",
                status="completed",
            )
        )
        db.add(
            Chunk(
                id=chunk_id,
                document_id=doc_id,
                knowledge_base_id=kb_id,
                content="冷知识测试块 content for governance e2e",
                chunk_index=0,
                char_count=40,
                is_active=True,
                hit_count=0,
            )
        )
        await db.commit()

    return {"kb_id": kb_id, "chunk_id": chunk_id}


@pytest.mark.asyncio
async def test_governance_workflow_scan_to_verify(kb_with_chunk):
    """scan→persist→approve→execute→verify 全链路 + 审计日志。"""
    kb_id = kb_with_chunk["kb_id"]
    chunk_id = kb_with_chunk["chunk_id"]

    fake_scan = {
        "kb_id": kb_id,
        "scanned_at": datetime.utcnow().isoformat(),
        "health": {
            "cold_count_90d": 1,
            "cold_count_total": 1,
            "threshold_days": 90,
            "total_chunks": 1,
            "active_chunks": 1,
            "suggestions_count": 1,
        },
        "suggestions": [
            {
                "id": "cold_stale:test0001",
                "type": "cold_stale",
                "title": "冷知识块 #0",
                "description": "测试冷知识建议",
                "chunk_ids": [chunk_id],
                "recommended_action": "archive",
                "severity": "warning",
                "content_preview": "冷知识测试块",
            }
        ],
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch.object(
            GovernanceService,
            "scan_suggestions",
            new_callable=AsyncMock,
            return_value=fake_scan,
        ):
            with patch.object(
                GovernanceService,
                "_sync_chunks_removal",
                new_callable=AsyncMock,
            ):
                scan_res = await client.post(
                    f"/api/knowledge-bases/{kb_id}/governance/suggestions/scan",
                    params={"scan_duplicates": "false"},
                )
                assert scan_res.status_code == 200, scan_res.text
                body = scan_res.json()
                assert body["new_suggestions"] >= 1

                pending_res = await client.get(
                    f"/api/knowledge-bases/{kb_id}/governance/suggestions/persisted",
                    params={"status": "pending"},
                )
                assert pending_res.status_code == 200
                pending = pending_res.json()
                assert len(pending) >= 1
                suggestion_id = pending[0]["id"]
                assert pending[0]["status"] == "pending"
                assert json.loads(pending[0]["chunk_ids"]) == [chunk_id]

                approve_res = await client.post(
                    f"/api/knowledge-bases/{kb_id}/governance/suggestions/{suggestion_id}/approve",
                )
                assert approve_res.status_code == 200
                assert approve_res.json()["status"] == "approved"

                execute_res = await client.post(
                    f"/api/knowledge-bases/{kb_id}/governance/suggestions/{suggestion_id}/execute",
                )
                assert execute_res.status_code == 200
                exec_body = execute_res.json()
                assert exec_body["status"] == "executed"
                assert exec_body["result"]["applied"] >= 1

                verify_res = await client.post(
                    f"/api/knowledge-bases/{kb_id}/governance/suggestions/{suggestion_id}/verify",
                )
                assert verify_res.status_code == 200
                assert verify_res.json()["status"] == "verified"

                audit_res = await client.get(
                    f"/api/knowledge-bases/{kb_id}/governance/audit-log",
                    params={"limit": 20},
                )
                assert audit_res.status_code == 200
                actions = [row["action"] for row in audit_res.json()]
                assert "approved" in actions
                assert "executed" in actions
                assert "verified" in actions

    async with async_session() as db:
        chunk = await db.get(Chunk, chunk_id)
        assert chunk is not None
        assert chunk.is_active is False

        row = await db.get(GovernanceSuggestion, suggestion_id)
        assert row is not None
        assert row.status == "verified"


@pytest.mark.asyncio
async def test_governance_dismiss_from_pending(kb_with_chunk):
    """pending 建议可驳回并写入审计。"""
    kb_id = kb_with_chunk["kb_id"]
    chunk_id = kb_with_chunk["chunk_id"]

    async with async_session() as db:
        row = GovernanceSuggestion(
            kb_id=kb_id,
            suggestion_type="cold_stale",
            title="待驳回",
            description="dismiss test",
            chunk_ids=json.dumps([chunk_id]),
            recommended_action="archive",
            severity="warning",
            status="pending",
        )
        db.add(row)
        await db.commit()
        suggestion_id = row.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        dismiss_res = await client.post(
            f"/api/knowledge-bases/{kb_id}/governance/suggestions/{suggestion_id}/dismiss",
            params={"reason": "误报"},
        )
        assert dismiss_res.status_code == 200
        assert dismiss_res.json()["status"] == "dismissed"

        audit_res = await client.get(
            f"/api/knowledge-bases/{kb_id}/governance/audit-log",
        )
        assert any(
            a["action"] == "dismissed" and a["suggestion_id"] == suggestion_id
            for a in audit_res.json()
        )
