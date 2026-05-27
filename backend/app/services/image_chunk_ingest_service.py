"""图片类 chunk 入库（Vision 描述 + embed_image）— Phase 4.1/4.2 共用"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.chroma_client import get_collection
from ..core.config import settings
from ..models.chunk import Chunk
from .embedding_service import EmbeddingService
from .ingestion_gate_service import IngestStats, ingest_text_chunks
from .vision_caption_service import describe_image

logger = logging.getLogger(__name__)


@dataclass
class ImageChunkSpec:
    image_path: str
    content_header: str
    filename_hint: str
    media_type: str = "image"
    extra_metadata: dict = field(default_factory=dict)


async def ingest_image_chunk_specs(
    db: AsyncSession,
    kb_id: str,
    doc_id: str,
    specs: list[ImageChunkSpec],
    *,
    start_chunk_index: int = 0,
    exclude_chunk_ids: set[str] | None = None,
) -> tuple[list[Chunk], list[str], IngestStats]:
    """按 spec 生成描述文本 chunk，并用对应图片路径做 embed_image。"""
    if not specs:
        return [], [], IngestStats()

    embed_svc = EmbeddingService()
    collection = get_collection(kb_id)
    records: list[Chunk] = []
    paths: list[str] = []
    stats = IngestStats()
    next_index = start_chunk_index

    for spec in specs:
        caption = await describe_image(spec.image_path, filename=spec.filename_hint)
        text = f"{spec.content_header}\n\n{caption}"
        batch, batch_stats = await ingest_text_chunks(
            db,
            kb_id,
            doc_id,
            [text],
            start_chunk_index=next_index,
            exclude_chunk_ids=exclude_chunk_ids,
        )
        stats.allowed += batch_stats.allowed
        stats.duplicates += batch_stats.duplicates
        stats.conflicts += batch_stats.conflicts
        stats.llm_calls += batch_stats.llm_calls

        if not batch:
            continue

        rec = batch[0]
        meta = {
            "document_id": doc_id,
            "chunk_index": rec.chunk_index,
            "media_type": spec.media_type,
            **spec.extra_metadata,
        }
        vec = embed_svc.embed_image(spec.image_path)
        collection.add(
            ids=[rec.id],
            embeddings=[vec],
            documents=[rec.content],
            metadatas=[meta],
        )
        db.add(rec)
        records.append(rec)
        paths.append(spec.image_path)
        next_index = rec.chunk_index + 1

    return records, paths, stats


async def ingest_pdf_embedded_images(
    db: AsyncSession,
    kb_id: str,
    doc_id: str,
    pdf_path: str,
    filename: str,
    *,
    start_chunk_index: int = 0,
    exclude_chunk_ids: set[str] | None = None,
) -> tuple[list[Chunk], IngestStats]:
    """提取 PDF 内嵌图并入库为独立 chunk。"""
    from .pdf_image_extractor import extract_pdf_images

    if not settings.PDF_IMAGE_EXTRACTION_ENABLED:
        return [], IngestStats()

    upload_root = Path(settings.UPLOAD_DIR)
    if not upload_root.is_absolute():
        from ..core.config import BASE_DIR

        upload_root = BASE_DIR / upload_root

    out_dir = upload_root / f"{doc_id}_pdfimg"
    embedded = extract_pdf_images(
        pdf_path,
        out_dir,
        min_dimension=settings.PDF_IMAGE_MIN_DIMENSION,
        max_images=settings.PDF_IMAGE_MAX_PER_DOCUMENT,
    )
    if not embedded:
        return [], IngestStats()

    specs = [
        ImageChunkSpec(
            image_path=img.path,
            content_header=(
                f"[PDF图片] {filename} 第{img.page_num}页 图{img.image_index}"
                f"（{img.width}×{img.height}）"
            ),
            filename_hint=f"{filename}-p{img.page_num}-i{img.image_index}.png",
            media_type="pdf_image",
            extra_metadata={"page": img.page_num, "image_index": img.image_index},
        )
        for img in embedded
    ]

    records, _, stats = await ingest_image_chunk_specs(
        db,
        kb_id,
        doc_id,
        specs,
        start_chunk_index=start_chunk_index,
        exclude_chunk_ids=exclude_chunk_ids,
    )
    logger.info(
        "pdf_image_ingest: doc=%s extracted=%s ingested=%s",
        doc_id,
        len(embedded),
        len(records),
    )
    return records, stats
