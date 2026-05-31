"""Phase 4.2 PDF 内嵌图验收 — 零真实 API（LLM_MOCK_MODE=true）"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

import fitz

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ["LLM_MOCK_MODE"] = "true"
os.environ["PDF_IMAGE_EXTRACTION_ENABLED"] = "true"


def _build_sample_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "verify phase42 sentinel Q7Z9", fontsize=12)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 56, 56))
    page.insert_image(fitz.Rect(72, 100, 128, 156), pixmap=pix)
    doc.save(path)
    doc.close()


async def main() -> int:
    from app.core.chroma_client import get_collection
    from app.core.database import async_session, init_db
    from app.models.chunk import Chunk
    from app.models.document import Document
    from app.models.knowledge_base import KnowledgeBase
    from app.services.document_service import _process_document
    from app.services.pdf_image_extractor import extract_pdf_images
    from sqlalchemy import select

    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb-p42-{suffix}"
    doc_id = f"d-p42-{suffix}"
    pdf = BACKEND / "data" / "smoke" / f"phase42-{suffix}.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    _build_sample_pdf(pdf)

    imgs = extract_pdf_images(pdf, pdf.parent / f"{doc_id}_img", min_dimension=32, max_images=5)
    assert imgs, "extract_pdf_images returned empty"

    async with async_session() as db:
        db.add(
            KnowledgeBase(
                id=kb_id,
                name="p42",
                embedding_model="m",
                chunk_size=200,
                chunk_overlap=20,
            )
        )
        db.add(
            Document(
                id=doc_id,
                knowledge_base_id=kb_id,
                filename="phase42.pdf",
                file_type="pdf",
                file_path=str(pdf),
                status="processing",
            )
        )
        await db.commit()

    await _process_document(doc_id, kb_id, "pdf", str(pdf))

    async with async_session() as db:
        doc = await db.get(Document, doc_id)
        assert doc and doc.status == "completed" and doc.chunk_count >= 2

        chunks = (
            (await db.execute(select(Chunk).where(Chunk.document_id == doc_id))).scalars().all()
        )
        text_hit = any("Q7Z9" in c.content for c in chunks)
        img_hit = any(c.content.startswith("[PDF图片]") for c in chunks)
        assert text_hit and img_hit

        img_chunk = next(c for c in chunks if c.content.startswith("[PDF图片]"))
        coll = get_collection(kb_id)
        got = coll.get(ids=[img_chunk.id], include=["metadatas"])
        assert got["metadatas"][0].get("media_type") == "pdf_image"

    print("PASS: Phase 4.2 PDF embedded images — extract + text chunks + pdf_image chunks")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
