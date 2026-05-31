"""文档服务"""

import logging
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import BackgroundTasks, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.chroma_client import get_collection
from ..core.config import settings
from ..core.database import async_session
from ..models.chunk import Chunk
from ..models.document import Document
from ..schemas.document import DocumentResponse, ManualDocumentCreate
from .ingestion_gate_service import IngestStats, ingest_text_chunks
from .media_utils import IMAGE_EXTENSIONS

logger = logging.getLogger(__name__)


def resolve_upload_path(file_path: str | None) -> Path:
    """解析 DB 中的 file_path（可能为相对路径 uploads/xxx）为可读的绝对路径。"""
    if not file_path:
        raise FileNotFoundError("文档缺少 file_path")
    p = Path(file_path)
    if p.is_file():
        return p.resolve()
    upload_root = Path(settings.UPLOAD_DIR)
    for cand in (upload_root / p.name, upload_root / p, p):
        if cand.is_file():
            return cand.resolve()
    raise FileNotFoundError(f"找不到上传文件: {file_path}")


async def _sync_chunks_to_fts(db: AsyncSession, kb_id: str, chunk_records: list[Chunk]) -> None:
    """入库后同步 FTS5（与 Chroma 写入配套，保证 BM25 可检索）。"""
    if not chunk_records:
        return
    from .fts_service import upsert_chunk_fts

    for c in chunk_records:
        await upsert_chunk_fts(
            db,
            c.id,
            kb_id,
            c.content,
            active=bool(c.is_active if c.is_active is not None else True),
        )
    await db.commit()


async def _sync_chunks_to_graph(db: AsyncSession, kb_id: str, chunk_records: list[Chunk]) -> None:
    """入库后同步轻量知识图谱三元组。"""
    if not chunk_records:
        return
    from .graph_store_service import sync_chunk_graph

    for c in chunk_records:
        await sync_chunk_graph(
            db,
            kb_id,
            c.id,
            c.document_id,
            c.content,
            active=bool(c.is_active if c.is_active is not None else True),
        )


class DocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_kb(
        self, kb_id: str, page: int, page_size: int
    ) -> tuple[list[DocumentResponse], int]:
        query = select(Document).where(Document.knowledge_base_id == kb_id)
        count_query = select(func.count(Document.id)).where(Document.knowledge_base_id == kb_id)

        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.order_by(Document.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        docs = result.scalars().all()
        return [DocumentResponse.model_validate(d) for d in docs], total

    async def upload(
        self, kb_id: str, file: UploadFile, background_tasks: BackgroundTasks
    ) -> DocumentResponse:
        ext = Path(file.filename or "").suffix.lower()
        text_map = {".pdf": "pdf", ".md": "md", ".txt": "txt"}
        if ext in IMAGE_EXTENSIONS:
            if not getattr(settings, "MULTIMODAL_IMAGE_ENABLED", True):
                raise ValueError("图片上传未启用（MULTIMODAL_IMAGE_ENABLED=false）")
            file_type = "image"
            max_sz = getattr(settings, "MAX_IMAGE_UPLOAD_SIZE", 10 * 1024 * 1024)
            if file.size and file.size > max_sz:
                raise ValueError(f"图片大小超过限制 ({max_sz // 1048576}MB)")
        else:
            if ext not in text_map:
                raise ValueError(f"不支持的文件类型: {ext}，仅支持 PDF/Markdown/TXT 或图片")
            file_type = text_map[ext]

        doc_id = str(uuid.uuid4())
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = (upload_dir / f"{doc_id}{ext}").resolve()

        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        doc = Document(
            id=doc_id,
            knowledge_base_id=kb_id,
            filename=file.filename or "unknown",
            file_type=file_type,
            file_path=str(file_path),
            file_size=file.size,
            status="processing",
        )
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)

        if file_type == "image":
            background_tasks.add_task(
                _process_image,
                doc_id,
                kb_id,
                file_type,
                str(file_path),
                file.filename or "unknown",
            )
        else:
            background_tasks.add_task(
                _process_document,
                doc_id,
                kb_id,
                file_type,
                str(file_path),
            )
        return DocumentResponse.model_validate(doc)

    async def create_manual(
        self, kb_id: str, data: ManualDocumentCreate, background_tasks: BackgroundTasks
    ) -> DocumentResponse:
        doc_id = str(uuid.uuid4())
        doc = Document(
            id=doc_id,
            knowledge_base_id=kb_id,
            filename=data.title,
            file_type="manual",
            status="processing",
        )
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)

        background_tasks.add_task(_process_manual, doc_id, kb_id, data.title, data.content)
        return DocumentResponse.model_validate(doc)

    async def ingest_manual_immediate(
        self, kb_id: str, title: str, content: str
    ) -> tuple[DocumentResponse, IngestStats]:
        """同步入库（Gap 批准 / 对话提炼确认），经门禁后写入。"""
        from .chunking_service import TextChunker

        doc_id = str(uuid.uuid4())
        doc = Document(
            id=doc_id,
            knowledge_base_id=kb_id,
            filename=title,
            file_type="manual",
            status="processing",
        )
        self.db.add(doc)
        await self.db.flush()

        from ..models.knowledge_base import KnowledgeBase

        kb_result = await self.db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
        kb = kb_result.scalar_one_or_none()
        chunk_size = kb.chunk_size if kb else settings.DEFAULT_CHUNK_SIZE
        chunk_overlap = kb.chunk_overlap if kb else settings.DEFAULT_CHUNK_OVERLAP

        chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks = chunker.split(content) or [content]

        chunk_records, gate_stats = await ingest_text_chunks(self.db, kb_id, doc_id, chunks)
        if chunk_records:
            from .embedding_service import EmbeddingService

            embed_svc = EmbeddingService()
            embeddings = embed_svc.embed_documents([c.content for c in chunk_records])
            self.db.add_all(chunk_records)
            collection = get_collection(kb_id)
            collection.add(
                ids=[c.id for c in chunk_records],
                embeddings=embeddings,
                documents=[c.content for c in chunk_records],
                metadatas=[
                    {"document_id": doc_id, "chunk_index": c.chunk_index} for c in chunk_records
                ],
            )

        doc.status = "completed"
        doc.chunk_count = len(chunk_records)
        doc.char_count = sum(len(c.content) for c in chunk_records)
        doc.ingest_duplicate_count = gate_stats.duplicates
        doc.ingest_conflict_count = gate_stats.conflicts
        await self.db.commit()
        await self.db.refresh(doc)
        await _sync_chunks_to_fts(self.db, kb_id, chunk_records)
        await _sync_chunks_to_graph(self.db, kb_id, chunk_records)
        return DocumentResponse.model_validate(doc), gate_stats

    async def get_by_id(self, doc_id: str) -> DocumentResponse | None:
        doc = await self.db.get(Document, doc_id)
        return DocumentResponse.model_validate(doc) if doc else None

    async def delete(self, doc_id: str):
        doc = await self.db.get(Document, doc_id)
        if doc:
            if doc.file_path:
                try:
                    Path(doc.file_path).unlink(missing_ok=True)
                except Exception:
                    pass
            # 清理 Chroma 中该文档的所有向量
            try:
                from sqlalchemy import select as _select

                from ..core.chroma_client import get_collection
                from ..models.chunk import Chunk

                chunk_ids = (
                    (await self.db.execute(_select(Chunk.id).where(Chunk.document_id == doc_id)))
                    .scalars()
                    .all()
                )
                if chunk_ids:
                    collection = get_collection(doc.knowledge_base_id)
                    collection.delete(ids=list(chunk_ids))
            except Exception:
                pass
            await self.db.delete(doc)
            await self.db.commit()

    async def toggle_status(self, doc_id: str, is_active: bool) -> DocumentResponse:
        doc = await self.db.get(Document, doc_id)
        doc.is_active = is_active
        await self.db.commit()
        await self.db.refresh(doc)

        # 同步 Chroma：禁用时删除所有向量，启用时重新向量化
        from ..core.chroma_client import get_collection
        from ..models.chunk import Chunk
        from .embedding_service import EmbeddingService

        result = await self.db.execute(select(Chunk).where(Chunk.document_id == doc_id))
        chunks = result.scalars().all()
        if chunks:
            collection = get_collection(doc.knowledge_base_id)
            if is_active:
                embed_svc = EmbeddingService()
                for chunk in chunks:
                    chunk.is_active = True
                    if doc.file_type == "image" and doc.file_path:
                        embedding = embed_svc.embed_image(doc.file_path)
                    else:
                        embedding = embed_svc.embed_query(chunk.content)
                    collection.upsert(
                        ids=[chunk.id],
                        embeddings=[embedding],
                        documents=[chunk.content],
                        metadatas=[{"document_id": doc_id, "chunk_index": chunk.chunk_index}],
                    )
            else:
                for chunk in chunks:
                    chunk.is_active = False
                collection.delete(ids=[c.id for c in chunks])
            await self.db.commit()
            await _sync_chunks_to_fts(self.db, doc.knowledge_base_id, chunks)
            await _sync_chunks_to_graph(self.db, doc.knowledge_base_id, chunks)

        return DocumentResponse.model_validate(doc)


async def _process_document(doc_id: str, kb_id: str, file_type: str, file_path: str):
    """后台处理上传的文档：解析 → 分块 → 向量化 → Chroma 写入；PDF 另提取内嵌图。"""
    from .chunking_service import DocumentParser, TextChunker
    from .embedding_service import EmbeddingService
    from .image_chunk_ingest_service import ingest_pdf_embedded_images

    async with async_session() as db:
        try:
            resolved = str(resolve_upload_path(file_path))
            text = DocumentParser.parse(resolved, file_type)

            from ..models.knowledge_base import KnowledgeBase

            kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
            kb = kb_result.scalar_one_or_none()
            chunk_size = kb.chunk_size if kb else settings.DEFAULT_CHUNK_SIZE
            chunk_overlap = kb.chunk_overlap if kb else settings.DEFAULT_CHUNK_OVERLAP

            chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            text_parts = chunker.split(text) if text and text.strip() else []

            chunk_records: list[Chunk] = []
            gate_stats = IngestStats()

            if text_parts:
                chunk_records, gate_stats = await ingest_text_chunks(db, kb_id, doc_id, text_parts)

                if chunk_records:
                    embed_svc = EmbeddingService()
                    embeddings = embed_svc.embed_documents([c.content for c in chunk_records])
                    db.add_all(chunk_records)
                    collection = get_collection(kb_id)
                    collection.add(
                        ids=[c.id for c in chunk_records],
                        embeddings=embeddings,
                        documents=[c.content for c in chunk_records],
                        metadatas=[
                            {
                                "document_id": doc_id,
                                "chunk_index": c.chunk_index,
                                "media_type": "text",
                            }
                            for c in chunk_records
                        ],
                    )

            doc_row = await db.get(Document, doc_id)
            filename = doc_row.filename if doc_row else Path(file_path).name

            if file_type == "pdf" and settings.PDF_IMAGE_EXTRACTION_ENABLED:
                text_ids = {c.id for c in chunk_records}
                img_records, img_stats = await ingest_pdf_embedded_images(
                    db,
                    kb_id,
                    doc_id,
                    resolved,
                    filename,
                    start_chunk_index=len(chunk_records),
                    exclude_chunk_ids=text_ids,
                )
                gate_stats.allowed += img_stats.allowed
                gate_stats.duplicates += img_stats.duplicates
                gate_stats.conflicts += img_stats.conflicts
                gate_stats.llm_calls += img_stats.llm_calls
                chunk_records.extend(img_records)

            doc = await db.get(Document, doc_id)
            if not chunk_records:
                if gate_stats.duplicates > 0 and doc:
                    doc.status = "completed"
                    doc.chunk_count = 0
                    doc.char_count = 0
                    doc.ingest_duplicate_count = gate_stats.duplicates
                    doc.ingest_conflict_count = gate_stats.conflicts
                    await db.commit()
                    return
                raise ValueError("未能从文件中提取有效文本或图片")

            if doc:
                doc.status = "completed"
                doc.chunk_count = len(chunk_records)
                doc.char_count = sum(len(c.content) for c in chunk_records)
                doc.ingest_duplicate_count = gate_stats.duplicates
                doc.ingest_conflict_count = gate_stats.conflicts

            await db.commit()
            await _sync_chunks_to_fts(db, kb_id, chunk_records)
            await _sync_chunks_to_graph(db, kb_id, chunk_records)

        except Exception:
            logger.exception("document ingest failed doc_id=%s", doc_id)
            doc = await db.get(Document, doc_id)
            if doc:
                doc.status = "error"
            await db.commit()


async def _process_image(
    doc_id: str,
    kb_id: str,
    file_type: str,
    file_path: str,
    filename: str,
):
    """后台处理图片：Vision 描述 → 单块入库 → 多模态向量写入 Chroma。"""
    from .image_chunk_ingest_service import ImageChunkSpec, ingest_image_chunk_specs

    async with async_session() as db:
        try:
            resolved = str(resolve_upload_path(file_path))
            spec = ImageChunkSpec(
                image_path=resolved,
                content_header=f"[图片文档] {filename}",
                filename_hint=filename,
                media_type="image",
            )
            chunk_records, _, gate_stats = await ingest_image_chunk_specs(db, kb_id, doc_id, [spec])

            if not chunk_records:
                raise ValueError("图片未通过入库门禁或处理失败")

            doc = await db.get(Document, doc_id)
            if doc:
                doc.status = "completed"
                doc.chunk_count = len(chunk_records)
                doc.char_count = sum(len(c.content) for c in chunk_records)
                doc.ingest_duplicate_count = gate_stats.duplicates
                doc.ingest_conflict_count = gate_stats.conflicts

            await db.commit()
            await _sync_chunks_to_fts(db, kb_id, chunk_records)
            await _sync_chunks_to_graph(db, kb_id, chunk_records)

        except Exception:
            logger.exception("image ingest failed doc_id=%s", doc_id)
            doc = await db.get(Document, doc_id)
            if doc:
                doc.status = "error"
            await db.commit()


async def recover_stuck_documents(min_stuck_minutes: int = 3) -> int:
    """恢复 status=processing 的文档（服务重启 / reload 导致后台任务丢失）。"""
    from sqlalchemy import select

    from ..models.document import Document

    cutoff = datetime.utcnow() - timedelta(minutes=min_stuck_minutes)
    async with async_session() as db:
        result = await db.execute(
            select(Document).where(
                Document.status == "processing",
                Document.created_at < cutoff,
            )
        )
        docs = list(result.scalars().all())

    if not docs:
        return 0

    logger.info("recovering %s stuck document(s) in processing", len(docs))
    for doc in docs:
        if not doc.file_path:
            async with async_session() as db:
                row = await db.get(Document, doc.id)
                if row:
                    row.status = "error"
                    await db.commit()
            continue
        try:
            if doc.file_type == "image":
                await _process_image(
                    doc.id, doc.knowledge_base_id, doc.file_type, doc.file_path, doc.filename
                )
            else:
                await _process_document(
                    doc.id, doc.knowledge_base_id, doc.file_type or "txt", doc.file_path
                )
        except Exception:
            logger.exception("recover failed doc_id=%s", doc.id)
    return len(docs)


async def _process_manual(doc_id: str, kb_id: str, title: str, content: str):
    """后台处理手动录入的知识"""
    from .chunking_service import TextChunker
    from .embedding_service import EmbeddingService

    async with async_session() as db:
        try:
            # 1. 获取分块配置
            from ..models.knowledge_base import KnowledgeBase

            kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
            kb = kb_result.scalar_one_or_none()
            chunk_size = kb.chunk_size if kb else settings.DEFAULT_CHUNK_SIZE
            chunk_overlap = kb.chunk_overlap if kb else settings.DEFAULT_CHUNK_OVERLAP

            # 2. 分块
            chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            chunks = chunker.split(content)
            if not chunks:
                chunks = [content]

            from .ingestion_gate_service import ingest_text_chunks

            chunk_records, gate_stats = await ingest_text_chunks(db, kb_id, doc_id, chunks)

            if chunk_records:
                embed_svc = EmbeddingService()
                embeddings = embed_svc.embed_documents([c.content for c in chunk_records])
                db.add_all(chunk_records)
                try:
                    collection = get_collection(kb_id)
                    collection.add(
                        ids=[c.id for c in chunk_records],
                        embeddings=embeddings,
                        documents=[c.content for c in chunk_records],
                        metadatas=[
                            {"document_id": doc_id, "chunk_index": c.chunk_index}
                            for c in chunk_records
                        ],
                    )
                except Exception as e:
                    raise RuntimeError(f"Chroma 写入失败: {e}") from e

            doc = await db.get(Document, doc_id)
            if doc:
                doc.status = "completed"
                doc.chunk_count = len(chunk_records)
                doc.char_count = sum(len(c.content) for c in chunk_records)
                doc.ingest_duplicate_count = gate_stats.duplicates
                doc.ingest_conflict_count = gate_stats.conflicts

            await db.commit()
            if chunk_records:
                await _sync_chunks_to_fts(db, kb_id, chunk_records)
                await _sync_chunks_to_graph(db, kb_id, chunk_records)

        except Exception:
            logger.exception("manual ingest failed doc_id=%s", doc_id)
            doc = await db.get(Document, doc_id)
            if doc:
                doc.status = "error"
            await db.commit()
