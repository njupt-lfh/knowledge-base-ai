"""Phase 4.2 PDF 内嵌图入库 — mock 集成"""

import os
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import fitz
import pytest

os.environ["LLM_MOCK_MODE"] = "true"
os.environ["PDF_IMAGE_EXTRACTION_ENABLED"] = "true"


def _pdf_with_text_and_image(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "PDF phase42 unique marker XYZ123", fontsize=14)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 48, 48))
    page.insert_image(fitz.Rect(72, 120, 120, 168), pixmap=pix)
    doc.save(path)
    doc.close()


@pytest.mark.asyncio
async def test_process_document_pdf_with_embedded_image(tmp_path: Path):
    from sqlalchemy import select

    from app.core.chroma_client import get_collection
    from app.core.database import async_session, init_db
    from app.models.chunk import Chunk
    from app.models.document import Document
    from app.models.knowledge_base import KnowledgeBase
    from app.services.document_service import _process_document
    from app.services.embedding_service import EmbeddingService

    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb-p42-{suffix}"
    doc_id = f"d-p42-{suffix}"
    pdf = tmp_path / "sample.pdf"
    _pdf_with_text_and_image(pdf)

    async with async_session() as db:
        db.add(
            KnowledgeBase(
                id=kb_id,
                name="t",
                embedding_model="m",
                chunk_size=200,
                chunk_overlap=20,
            )
        )
        db.add(
            Document(
                id=doc_id,
                knowledge_base_id=kb_id,
                filename="sample.pdf",
                file_type="pdf",
                file_path=str(pdf),
                status="processing",
            )
        )
        await db.commit()

    with patch.object(
        EmbeddingService,
        "embed_image",
        return_value=[float(i % 13) for i in range(256)],
    ):
        await _process_document(doc_id, kb_id, "pdf", str(pdf))

    async with async_session() as db:
        doc = await db.get(Document, doc_id)
        assert doc.status == "completed"
        assert doc.chunk_count >= 2

        chunks = (
            await db.execute(
                select(Chunk).where(Chunk.document_id == doc_id).order_by(Chunk.chunk_index)
            )
        ).scalars().all()
        assert any("XYZ123" in c.content for c in chunks)
        pdf_img = [c for c in chunks if c.content.startswith("[PDF图片]")]
        assert len(pdf_img) >= 1

        coll = get_collection(kb_id)
        meta = coll.get(ids=[pdf_img[0].id], include=["metadatas"])
        assert meta["metadatas"][0]["media_type"] == "pdf_image"
