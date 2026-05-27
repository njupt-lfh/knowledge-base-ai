"""文件夹同步 — Phase 4.4"""

import os
import uuid
from pathlib import Path

import pytest

os.environ.setdefault("LLM_MOCK_MODE", "true")


@pytest.mark.asyncio
async def test_scan_watch_imports_new_txt(tmp_path: Path):
    from app.core.database import async_session, init_db
    from app.models.kb_folder_watch import KbFolderWatch
    from app.models.knowledge_base import KnowledgeBase
    from app.services.folder_sync_service import scan_watch

    await init_db()
    kb_id = f"kb-sync-{uuid.uuid4().hex[:8]}"
    watch_dir = tmp_path / "inbox"
    watch_dir.mkdir()
    sample = watch_dir / "note.txt"
    sample.write_text("folder sync unique marker Z9SYNC", encoding="utf-8")

    async with async_session() as db:
        db.add(
            KnowledgeBase(
                id=kb_id,
                name="sync",
                embedding_model="m",
                chunk_size=200,
                chunk_overlap=20,
            )
        )
        watch = KbFolderWatch(
            knowledge_base_id=kb_id,
            folder_path=str(watch_dir),
            enabled=True,
            recursive=False,
        )
        db.add(watch)
        await db.commit()
        await db.refresh(watch)

        result = await scan_watch(db, watch)
        assert result.imported == 1
        assert result.scanned == 1
