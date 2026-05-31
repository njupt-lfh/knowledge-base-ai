"""Phase 4.4 文件夹监听验收"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ["LLM_MOCK_MODE"] = "true"


async def main() -> int:
    from app.core.database import async_session, init_db
    from app.models.chunk import Chunk
    from app.models.document import Document
    from app.models.kb_folder_watch import KbFolderWatch
    from app.models.knowledge_base import KnowledgeBase
    from app.services.folder_sync_service import scan_watch
    from sqlalchemy import select

    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb-p44-{suffix}"
    inbox = BACKEND / "data" / "sync_inbox" / suffix
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "hello.txt").write_text("verify phase44 marker P44OK", encoding="utf-8")

    async with async_session() as db:
        db.add(
            KnowledgeBase(
                id=kb_id, name="p44", embedding_model="m", chunk_size=200, chunk_overlap=20
            )
        )
        watch = KbFolderWatch(knowledge_base_id=kb_id, folder_path=str(inbox), enabled=True)
        db.add(watch)
        await db.commit()
        await db.refresh(watch)

        r = await scan_watch(db, watch)
        assert r.imported == 1, f"imported={r.imported}"

        docs = (
            (await db.execute(select(Document).where(Document.knowledge_base_id == kb_id)))
            .scalars()
            .all()
        )
        assert len(docs) == 1 and docs[0].status == "completed"

        chunks = (
            (await db.execute(select(Chunk).where(Chunk.document_id == docs[0].id))).scalars().all()
        )
        assert chunks and "P44OK" in chunks[0].content

    print("PASS: Phase 4.4 folder watch — scan + import + ingest")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
