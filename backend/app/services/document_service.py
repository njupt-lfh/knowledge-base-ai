"""文档服务"""

import shutil
import uuid
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


class DocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_kb(self, kb_id: str, page: int, page_size: int) -> tuple[list[DocumentResponse], int]:
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

    async def upload(self, kb_id: str, file: UploadFile, background_tasks: BackgroundTasks) -> DocumentResponse:
        ext = Path(file.filename).suffix.lower()
        type_map = {".pdf": "pdf", ".md": "md", ".txt": "txt"}
        file_type = type_map.get(ext, "txt")

        doc_id = str(uuid.uuid4())
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / f"{doc_id}{ext}"

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

        background_tasks.add_task(_process_document, doc_id, kb_id, file_type, str(file_path))
        return DocumentResponse.model_validate(doc)

    async def create_manual(self, kb_id: str, data: ManualDocumentCreate, background_tasks: BackgroundTasks) -> DocumentResponse:
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
                chunk_ids = (await self.db.execute(
                    _select(Chunk.id).where(Chunk.document_id == doc_id)
                )).scalars().all()
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

        return DocumentResponse.model_validate(doc)


async def _process_document(doc_id: str, kb_id: str, file_type: str, file_path: str):
    """后台处理上传的文档：解析 → 分块 → 向量化 → Chroma 写入"""
    from .chunking_service import DocumentParser, TextChunker
    from .embedding_service import EmbeddingService

    async with async_session() as db:
        try:
            # 1. 解析文件提取文本
            text = DocumentParser.parse(file_path, file_type)

            # 2. 获取知识库的分块配置
            from ..models.knowledge_base import KnowledgeBase
            kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
            kb = kb_result.scalar_one_or_none()
            chunk_size = kb.chunk_size if kb else settings.DEFAULT_CHUNK_SIZE
            chunk_overlap = kb.chunk_overlap if kb else settings.DEFAULT_CHUNK_OVERLAP

            # 3. 分块
            chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            chunks = chunker.split(text)

            if not chunks:
                raise ValueError("未能从文件中提取有效文本")

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
                    raise RuntimeError(f"Chroma 写入失败: {e}")

            doc = await db.get(Document, doc_id)
            if doc:
                doc.status = "completed"
                doc.chunk_count = len(chunk_records)
                doc.char_count = sum(len(c.content) for c in chunk_records)
                doc.ingest_duplicate_count = gate_stats.duplicates
                doc.ingest_conflict_count = gate_stats.conflicts

            await db.commit()

        except Exception as e:
            doc = await db.get(Document, doc_id)
            if doc:
                doc.status = "error"
            await db.commit()
            raise e


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
                    raise RuntimeError(f"Chroma 写入失败: {e}")

            doc = await db.get(Document, doc_id)
            if doc:
                doc.status = "completed"
                doc.chunk_count = len(chunk_records)
                doc.char_count = sum(len(c.content) for c in chunk_records)
                doc.ingest_duplicate_count = gate_stats.duplicates
                doc.ingest_conflict_count = gate_stats.conflicts

            await db.commit()

        except Exception as e:
            doc = await db.get(Document, doc_id)
            if doc:
                doc.status = "error"
            await db.commit()
            raise e
