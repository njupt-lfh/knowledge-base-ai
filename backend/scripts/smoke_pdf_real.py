"""真实 API PDF 入库联调（文本 + 内嵌图）— 用法: python scripts/smoke_pdf_real.py <pdf路径> [kb_id]"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.config import settings  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_path", type=Path)
    parser.add_argument("kb_id", nargs="?", default="")
    args = parser.parse_args()

    pdf_src: Path = args.pdf_path
    if not pdf_src.is_file():
        print(f"FAIL: 文件不存在: {pdf_src}")
        return 1

    if settings.LLM_MOCK_MODE:
        print("FAIL: LLM_MOCK_MODE=true，请改为 false 后再联调")
        return 1
    if not settings.PDF_IMAGE_EXTRACTION_ENABLED:
        print("FAIL: PDF_IMAGE_EXTRACTION_ENABLED=false")
        return 1

    from sqlalchemy import select

    from app.core.chroma_client import get_collection
    from app.core.database import async_session, init_db
    from app.models.chunk import Chunk
    from app.models.document import Document
    from app.models.knowledge_base import KnowledgeBase
    from app.services.document_service import _process_document
    from app.services.embedding_service import EmbeddingService
    from app.services.pdf_image_extractor import extract_pdf_images

    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = args.kb_id.strip() or f"kb-smoke-p42-{suffix}"
    doc_id = f"d-smoke-p42-{suffix}"

    upload_dir = Path(settings.UPLOAD_DIR)
    if not upload_dir.is_absolute():
        upload_dir = BACKEND / upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"{doc_id}.pdf"
    shutil.copy2(pdf_src, dest)

    preview_dir = upload_dir / f"{doc_id}_preview"
    extracted = extract_pdf_images(
        dest,
        preview_dir,
        min_dimension=settings.PDF_IMAGE_MIN_DIMENSION,
        max_images=settings.PDF_IMAGE_MAX_PER_DOCUMENT,
    )

    print(f"源 PDF: {pdf_src} ({pdf_src.stat().st_size} bytes)")
    print(f"复制: {dest}")
    print(f"预检内嵌图: {len(extracted)} 张")
    for img in extracted[:5]:
        print(f"  - 第{img.page_num}页 图{img.image_index} {img.width}x{img.height} -> {Path(img.path).name}")
    if len(extracted) > 5:
        print(f"  ... 另有 {len(extracted) - 5} 张")

    print(f"LLM: {settings.VOLCENGINE_LLM_MODEL}")
    print(f"Embedding: {settings.VOLCENGINE_EMBEDDING_MODEL}")
    vision = (settings.VISION_CAPTION_MODEL or "").strip() or settings.VOLCENGINE_LLM_MODEL
    print(f"Vision: {vision}")
    print("处理中（文本分块 + 内嵌图 Vision/embed，耗时取决于图片数量）...")

    async with async_session() as db:
        if args.kb_id.strip():
            kb = await db.get(KnowledgeBase, kb_id)
            if not kb:
                print(f"FAIL: 知识库不存在: {kb_id}")
                return 1
        else:
            db.add(
                KnowledgeBase(
                    id=kb_id,
                    name=f"PDF联调-{suffix}",
                    embedding_model=settings.VOLCENGINE_EMBEDDING_MODEL,
                    chunk_size=settings.DEFAULT_CHUNK_SIZE,
                    chunk_overlap=settings.DEFAULT_CHUNK_OVERLAP,
                )
            )
        db.add(
            Document(
                id=doc_id,
                knowledge_base_id=kb_id,
                filename=pdf_src.name,
                file_type="pdf",
                file_path=str(dest),
                file_size=pdf_src.stat().st_size,
                status="processing",
            )
        )
        await db.commit()

    await _process_document(doc_id, kb_id, "pdf", str(dest))

    async with async_session() as db:
        doc = await db.get(Document, doc_id)
        if not doc or doc.status != "completed":
            print(f"FAIL: 文档状态={getattr(doc, 'status', None)}")
            return 1

        chunks = (
            await db.execute(
                select(Chunk)
                .where(Chunk.document_id == doc_id)
                .order_by(Chunk.chunk_index)
            )
        ).scalars().all()

        text_chunks = [c for c in chunks if not c.content.startswith("[PDF图片]")]
        img_chunks = [c for c in chunks if c.content.startswith("[PDF图片]")]

        print(f"\n--- 入库结果 ---")
        print(f"状态: {doc.status} | 总 chunk: {doc.chunk_count} | 文本: {len(text_chunks)} | PDF图: {len(img_chunks)}")
        print(f"重复跳过: {doc.ingest_duplicate_count} | 冲突: {doc.ingest_conflict_count}")

        if text_chunks:
            print(f"\n[文本 chunk 0 预览] ({len(text_chunks[0].content)} 字)")
            print(text_chunks[0].content[:400] + ("..." if len(text_chunks[0].content) > 400 else ""))

        for i, c in enumerate(img_chunks[:3]):
            print(f"\n[PDF图 chunk {c.chunk_index} 预览]")
            print(c.content[:500] + ("..." if len(c.content) > 500 else ""))

        coll = get_collection(kb_id)
        if img_chunks:
            got = coll.get(ids=[img_chunks[0].id], include=["metadatas"])
            meta = (got.get("metadatas") or [{}])[0]
            print(f"\nChroma 首图块: media_type={meta.get('media_type')} page={meta.get('page')}")

            embed_svc = EmbeddingService()
            q = "图表" if not img_chunks[0].content else img_chunks[0].content[20:40]
            res = coll.query(query_embeddings=[embed_svc.embed_query("文档中的图片和图表")], n_results=min(3, len(chunks)))
            ids = res["ids"][0] if res.get("ids") else []
            print(f"检索「文档中的图片和图表」Top-{len(ids)}: {ids[:3]}")

    print(f"\nPASS: PDF 真实入库联调 kb_id={kb_id} doc_id={doc_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
