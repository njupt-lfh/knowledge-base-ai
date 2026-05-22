"""知识块 API 路由"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..schemas.chunk import ChunkUpdate, ChunkResponse, SearchRequest, SearchResponse
from ..services.chunk_service import ChunkService

router = APIRouter(tags=["知识块"])


@router.get("/api/documents/{doc_id}/chunks", response_model=list[ChunkResponse])
async def list_chunks(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取文档的知识块列表"""
    service = ChunkService(db)
    return await service.list_by_document(doc_id)


@router.put("/api/chunks/{chunk_id}", response_model=ChunkResponse)
async def update_chunk(
    chunk_id: str,
    data: ChunkUpdate,
    db: AsyncSession = Depends(get_db),
):
    """编辑知识块"""
    service = ChunkService(db)
    chunk = await service.update(chunk_id, data)
    if not chunk:
        raise HTTPException(status_code=404, detail="知识块不存在")
    return chunk


@router.put("/api/chunks/{chunk_id}/status", response_model=ChunkResponse)
async def toggle_chunk_status(
    chunk_id: str,
    is_active: bool,
    db: AsyncSession = Depends(get_db),
):
    """切换知识块启用/禁用状态"""
    service = ChunkService(db)
    return await service.toggle_status(chunk_id, is_active)


@router.post("/api/knowledge-bases/{kb_id}/search", response_model=SearchResponse)
async def search_knowledge(
    kb_id: str,
    data: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """知识检索测试"""
    service = ChunkService(db)
    items = await service.search(kb_id, data.query, data.top_k)
    return SearchResponse(items=items, query=data.query)
