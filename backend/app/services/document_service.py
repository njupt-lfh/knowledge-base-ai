"""文档服务"""

import uuid
import shutil
from pathlib import Path
from datetime import datetime

from fastapi import UploadFile, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..core.config import settings
from ..models.document import Document
from ..models.chunk import Chunk
from ..schemas.document import DocumentResponse, ManualDocumentCreate
from ..core.chroma_client import get_collection


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

        background_tasks.add_task(self._process_document, doc_id, kb_id, file_type, str(file_path))
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

        background_tasks.add_task(self._process_manual, doc_id, kb_id, data.title, data.content)
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

    async def _process_document(self, doc_id: str, kb_id: str, file_type: str, file_path: str):
        """后台处理上传的文档：解析 + 分块 + 向量化"""
        from .chunking_service import DocumentParser, TextChunker
        from .embedding_service import EmbeddingService

        async with self.db.bind.begin() as conn:
            pass  # 在同步上下文中创建新的session比较复杂，这里留到后续完善

    async def _process_manual(self, doc_id: str, kb_id: str, title: str, content: str):
        """后台处理手动录入的知识"""
        pass  # 后续完善
