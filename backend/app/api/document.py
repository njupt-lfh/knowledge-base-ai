"""文档 API 路由"""

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.database import get_db
from ..models.document import Document
from ..schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    ManualDocumentCreate,
)
from ..services.document_service import DocumentService

router = APIRouter(prefix="/api/knowledge-bases/{kb_id}/documents", tags=["文档"])


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    kb_id: str,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    service = DocumentService(db)
    items, total = await service.list_by_kb(kb_id, page, page_size)
    return DocumentListResponse(items=items, total=total)


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    kb_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    if file.size and file.size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413, detail=f"文件大小超过限制 ({settings.MAX_UPLOAD_SIZE // 1048576}MB)"
        )
    service = DocumentService(db)
    return await service.upload(kb_id, file, background_tasks)


@router.post("/manual", response_model=DocumentResponse, status_code=201)
async def create_manual_document(
    kb_id: str,
    data: ManualDocumentCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    service = DocumentService(db)
    return await service.create_manual(kb_id, data, background_tasks)


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = DocumentService(db)
    doc = await service.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = DocumentService(db)
    await service.delete(doc_id)


@router.put("/{doc_id}/status", response_model=DocumentResponse)
async def toggle_document_status(
    kb_id: str,
    doc_id: str,
    is_active: bool = Form(...),
    db: AsyncSession = Depends(get_db),
):
    service = DocumentService(db)
    return await service.toggle_status(doc_id, is_active)


@router.post("/{doc_id}/reindex", response_model=DocumentResponse)
async def reindex_document(
    kb_id: str,
    doc_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """重新向量化文档"""
    from ..services.document_service import _process_document

    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    if not doc.file_path:
        raise HTTPException(status_code=400, detail="仅文件上传文档支持 reindex")
    doc.status = "processing"
    await db.commit()
    background_tasks.add_task(_process_document, doc_id, kb_id, doc.file_type, doc.file_path)
    return DocumentResponse.model_validate(doc)
