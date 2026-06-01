"""文档 API 路由。

提供文档分页列表、文件上传、手工录入、详情、删除、启用切换与 reindex 端点，
委托 `DocumentService` 处理解析、分块与向量化后台任务。
"""

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
    """分页获取知识库文档列表。

    参数:
        kb_id: 知识库 ID。
        page: 页码，从 1 开始。
        page_size: 每页条数。
        db: 数据库会话。

    返回:
        DocumentListResponse。
    """
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
    """上传文件并异步入库（分块+向量化）。

    参数:
        kb_id: 知识库 ID。
        background_tasks: FastAPI 后台任务队列。
        file: 上传文件。
        db: 数据库会话。

    返回:
        新建的 DocumentResponse；超大文件 413。
    """
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
    """创建手工文本文档并异步分块入库。

    参数:
        kb_id: 知识库 ID。
        data: 标题与正文。
        background_tasks: 后台任务队列。
        db: 数据库会话。

    返回:
        新建的 DocumentResponse。
    """
    service = DocumentService(db)
    return await service.create_manual(kb_id, data, background_tasks)


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取单个文档详情。

    参数:
        kb_id: 知识库 ID（路径参数）。
        doc_id: 文档 ID。
        db: 数据库会话。

    返回:
        DocumentResponse；不存在时 404。
    """
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
    """删除文档及其 chunk、向量与磁盘文件。

    参数:
        kb_id: 知识库 ID。
        doc_id: 文档 ID。
        db: 数据库会话。
    """
    service = DocumentService(db)
    await service.delete(doc_id)


@router.put("/{doc_id}/status", response_model=DocumentResponse)
async def toggle_document_status(
    kb_id: str,
    doc_id: str,
    is_active: bool = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """切换单个文档启用状态并同步向量索引。

    参数:
        kb_id: 知识库 ID。
        doc_id: 文档 ID。
        is_active: 目标状态（表单字段）。
        db: 数据库会话。

    返回:
        更新后的 DocumentResponse。
    """
    service = DocumentService(db)
    return await service.toggle_status(doc_id, is_active)


@router.post("/{doc_id}/reindex", response_model=DocumentResponse)
async def reindex_document(
    kb_id: str,
    doc_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """重新解析并向量化已上传文件文档。

    参数:
        kb_id: 知识库 ID。
        doc_id: 文档 ID。
        background_tasks: 后台任务队列。
        db: 数据库会话。

    返回:
        状态为 processing 的 DocumentResponse；无 file_path 时 400。
    """
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
