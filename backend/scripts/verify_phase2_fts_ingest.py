"""Phase 2 审计修复验收：上传/手动录入 → FTS5 同步"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


async def main() -> int:
    from sqlalchemy import text

    from app.core.database import async_session, init_db
    from app.models.document import Document
    from app.models.knowledge_base import KnowledgeBase
    from app.services.document_service import DocumentService, _process_document, _process_manual
    from app.services.fts_service import FTS_TABLE, search_fts

    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb-verify-fts-{suffix}"
    manual_doc_id = f"d-manual-v-{suffix}"
    upload_doc_id = f"d-upload-v-{suffix}"
    manual_kw = f"manualverify{suffix}"
    upload_kw = f"uploadverify{suffix}"

    async with async_session() as db:
        db.add(
            KnowledgeBase(
                id=kb_id,
                name="fts-verify",
                embedding_model="m",
                chunk_size=500,
                chunk_overlap=50,
            )
        )
        db.add(
            Document(
                id=manual_doc_id,
                knowledge_base_id=kb_id,
                filename="manual",
                file_type="manual",
                status="processing",
            )
        )
        db.add(
            Document(
                id=upload_doc_id,
                knowledge_base_id=kb_id,
                filename="sample.txt",
                file_type="txt",
                status="processing",
            )
        )
        await db.commit()

    fake_collection = MagicMock()
    embed_patch = patch(
        "app.services.embedding_service.EmbeddingService.embed_documents",
        return_value=[[0.1] * 256],
    )
    embed_query_patch = patch(
        "app.services.embedding_service.EmbeddingService.embed_query",
        return_value=[0.1] * 256,
    )
    chroma_patch = patch("app.services.document_service.get_collection", return_value=fake_collection)

    with embed_patch, embed_query_patch, chroma_patch:
        await _process_manual(
            manual_doc_id,
            kb_id,
            "manual",
            f"手动录入验收关键词 {manual_kw} 应进入 FTS5。",
        )
        with patch(
            "app.services.chunking_service.DocumentParser.parse",
            return_value=f"文件上传验收关键词 {upload_kw} 应进入 FTS5。",
        ):
            await _process_document(upload_doc_id, kb_id, "txt", "/tmp/fake.txt")

    async with async_session() as db:
        manual_hits = await search_fts(db, kb_id, manual_kw, limit=5)
        upload_hits = await search_fts(db, kb_id, upload_kw, limit=5)
        if not manual_hits:
            print("FAIL: manual ingest not in FTS5")
            return 1
        if not upload_hits:
            print("FAIL: upload ingest not in FTS5")
            return 1
        print(f"  manual_fts_hits={len(manual_hits)} upload_fts_hits={len(upload_hits)}")

        svc = DocumentService(db)
        await svc.toggle_status(manual_doc_id, False)
        disabled_hits = await search_fts(db, kb_id, manual_kw, limit=5)
        if disabled_hits:
            print("FAIL: toggle_status(false) should remove chunks from FTS5")
            return 1
        print("  toggle_status removes FTS ok")

        count = (
            await db.execute(
                text(f"SELECT COUNT(*) FROM {FTS_TABLE} WHERE knowledge_base_id = :kb"),
                {"kb": kb_id},
            )
        ).scalar_one()
        if count < 1:
            print("FAIL: upload chunks should remain in FTS after manual disable")
            return 1

    print("PASS: Phase 2 FTS ingest — manual + upload + toggle sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
