"""知识库 API 路由"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
    KnowledgeBaseListResponse,
)
from ..services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/api/knowledge-bases", tags=["知识库"])


@router.get("", response_model=KnowledgeBaseListResponse)
async def list_knowledge_bases(
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """获取知识库列表"""
    service = KnowledgeService(db)
    items, total = await service.list(page, page_size, search)
    return KnowledgeBaseListResponse(items=items, total=total)


@router.post("", response_model=KnowledgeBaseResponse, status_code=201)
async def create_knowledge_base(
    data: KnowledgeBaseCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建知识库"""
    service = KnowledgeService(db)
    return await service.create(data)


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取知识库详情"""
    service = KnowledgeService(db)
    kb = await service.get_by_id(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return kb


@router.put("/{kb_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(
    kb_id: str,
    data: KnowledgeBaseUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新知识库"""
    service = KnowledgeService(db)
    kb = await service.update(kb_id, data)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return kb


@router.delete("/{kb_id}", status_code=204)
async def delete_knowledge_base(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
):
    """删除知识库"""
    service = KnowledgeService(db)
    await service.delete(kb_id)
