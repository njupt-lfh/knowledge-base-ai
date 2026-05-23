"""文档服务"""

import shutil
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.database import async_session
from ..core.chroma_client import get_collection
from ..models.document import Document
from ..models.chunk import Chunk
from ..schemas.document import DocumentResponse, ManualDocumentCreate


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
            await self.db.delete(doc)
            await self.db.commit()

    async def toggle_status(self, doc_id: str, is_active: bool) -> DocumentResponse:
        doc = await self.db.get(Document, doc_id)
        doc.is_active = is_active
        await self.db.commit()
        await self.db.refresh(doc)
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

            # 4. 向量化
            embed_svc = EmbeddingService()
            embeddings = embed_svc.embed_documents(chunks)

            # 5. 写入 Chunk 表
            chunk_records = []
            for i, content in enumerate(chunks):
                chunk_records.append(Chunk(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    knowledge_base_id=kb_id,
                    content=content,
                    chunk_index=i,
                    char_count=len(content),
                ))
            db.add_all(chunk_records)

            # 6. 写入 Chroma 向量库
            try:
                collection = get_collection(kb_id)
                collection.add(
                    ids=[c.id for c in chunk_records],
                    embeddings=embeddings,
                    documents=[c.content for c in chunk_records],
                    metadatas=[{"document_id": doc_id, "chunk_index": i} for i in range(len(chunk_records))],
                )
            except Exception as e:
                raise RuntimeError(f"Chroma 写入失败: {e}")

            # 7. 更新文档状态
            doc = await db.get(Document, doc_id)
            if doc:
                doc.status = "completed"
                doc.chunk_count = len(chunks)
                doc.char_count = sum(len(c) for c in chunks)

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

            # 3. 向量化
            embed_svc = EmbeddingService()
            embeddings = embed_svc.embed_documents(chunks)

            # 4. 写入 Chunk 表
            chunk_records = []
            for i, text in enumerate(chunks):
                chunk_records.append(Chunk(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    knowledge_base_id=kb_id,
                    content=text,
                    chunk_index=i,
                    char_count=len(text),
                ))
            db.add_all(chunk_records)

            # 5. 写入 Chroma
            try:
                collection = get_collection(kb_id)
                collection.add(
                    ids=[c.id for c in chunk_records],
                    embeddings=embeddings,
                    documents=[c.content for c in chunk_records],
                    metadatas=[{"document_id": doc_id, "chunk_index": i} for i in range(len(chunk_records))],
                )
            except Exception as e:
                raise RuntimeError(f"Chroma 写入失败: {e}")

            # 6. 更新文档状态
            doc = await db.get(Document, doc_id)
            if doc:
                doc.status = "completed"
                doc.chunk_count = len(chunks)
                doc.char_count = sum(len(c) for c in chunks)

            await db.commit()

        except Exception as e:
            doc = await db.get(Document, doc_id)
            if doc:
                doc.status = "error"
            await db.commit()
            raise e
