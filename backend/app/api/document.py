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

from ..core.database import get_db
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
    """获取文档列表"""
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
    """上传文档（PDF/MD/TXT）"""
    service = DocumentService(db)
    return await service.upload(kb_id, file, background_tasks)


@router.post("/manual", response_model=DocumentResponse, status_code=201)
async def create_manual_document(
    kb_id: str,
    data: ManualDocumentCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """手动录入知识"""
    service = DocumentService(db)
    return await service.create_manual(kb_id, data, background_tasks)


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取文档详情"""
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
    """删除文档"""
    service = DocumentService(db)
    await service.delete(doc_id)


@router.put("/{doc_id}/status", response_model=DocumentResponse)
async def toggle_document_status(
    kb_id: str,
    doc_id: str,
    is_active: bool = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """切换文档启用/禁用状态"""
    service = DocumentService(db)
    return await service.toggle_status(doc_id, is_active)
