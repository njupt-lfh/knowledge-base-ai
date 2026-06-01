"""sync.py API — Phase 4.4 审计补充

验证内容：
  - sync.py 文件夹监听 CRUD 与 webhook 鉴权

运行方式（在 backend 目录）:
  pytest tests/test_sync_api.py -v

预期结果：全部用例通过。
"""

import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("LLM_MOCK_MODE", "true")

from app.core.database import async_session, init_db
from app.main import app
from app.models.knowledge_base import KnowledgeBase
from app.services.folder_sync_service import SyncScanResult


@pytest.fixture
async def kb_id():
    """kb_id 函数。"""
    await init_db()
    kid = f"kb-sync-api-{uuid.uuid4().hex[:8]}"
    async with async_session() as db:
        db.add(
            KnowledgeBase(
                id=kid,
                name="sync-api",
                embedding_model="m",
                chunk_size=200,
                chunk_overlap=20,
            )
        )
        await db.commit()
    return kid


@pytest.mark.asyncio
async def test_sync_watch_crud_and_scan(kb_id: str, tmp_path):
    """验证文件夹扫描导入。"""
    transport = ASGITransport(app=app)
    folder = tmp_path / "watch"
    folder.mkdir()

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create = await client.post(
            "/api/sync/watches",
            json={
                "knowledge_base_id": kb_id,
                "folder_path": str(folder),
                "enabled": True,
                "recursive": False,
            },
        )
        assert create.status_code == 201, create.text
        watch = create.json()
        watch_id = watch["id"]

        listed = await client.get("/api/sync/watches", params={"kb_id": kb_id})
        assert listed.status_code == 200
        assert any(w["id"] == watch_id for w in listed.json())

        patched = await client.patch(
            f"/api/sync/watches/{watch_id}",
            json={"recursive": True},
        )
        assert patched.status_code == 200
        assert patched.json()["recursive"] is True

        fake = SyncScanResult(
            watch_id=watch_id,
            kb_id=kb_id,
            scanned=2,
            imported=1,
            updated=0,
            skipped=1,
            errors=[],
        )
        with patch("app.api.sync.scan_watch", new_callable=AsyncMock, return_value=fake):
            scan = await client.post(f"/api/sync/watches/{watch_id}/scan")
        assert scan.status_code == 200
        body = scan.json()
        assert body["imported"] == 1
        assert body["scanned"] == 2

        deleted = await client.delete(f"/api/sync/watches/{watch_id}")
        assert deleted.status_code == 204

        missing = await client.get("/api/sync/watches", params={"kb_id": kb_id})
        assert not any(w["id"] == watch_id for w in missing.json())


@pytest.mark.asyncio
async def test_webhook_requires_secret_when_configured(kb_id: str, monkeypatch):
    """验证 webhook 鉴权。"""
    monkeypatch.setattr("app.api.sync.settings.SYNC_WEBHOOK_SECRET", "test-secret")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/sync/webhook/{kb_id}")
        assert res.status_code == 401

        with patch(
            "app.api.sync.scan_kb_watch",
            new_callable=AsyncMock,
            return_value=[],
        ):
            ok = await client.post(
                f"/api/sync/webhook/{kb_id}",
                headers={"X-Sync-Secret": "test-secret"},
            )
        assert ok.status_code == 404  # 无 watch 配置
