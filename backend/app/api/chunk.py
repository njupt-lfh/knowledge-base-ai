"""知识块 API 路由。

提供按文档列出 chunk、编辑内容、切换启用状态及知识库内检索测试端点，
委托 `ChunkService` 同步向量库与 FTS。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..schemas.chunk import ChunkResponse, ChunkUpdate, SearchRequest, SearchResponse
from ..services.chunk_service import ChunkService

router = APIRouter(tags=["知识块"])


@router.get("/api/documents/{doc_id}/chunks", response_model=list[ChunkResponse])
async def list_chunks(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取文档的知识块列表。

    参数:
        doc_id: 文档 ID。
        db: 数据库会话。

    返回:
        ChunkResponse 列表。
    """
    service = ChunkService(db)
    return await service.list_by_document(doc_id)


@router.put("/api/chunks/{chunk_id}", response_model=ChunkResponse)
async def update_chunk(
    chunk_id: str,
    data: ChunkUpdate,
    db: AsyncSession = Depends(get_db),
):
    """编辑知识块内容与/或启用状态。

    参数:
        chunk_id: 知识块 ID。
        data: 可选 content、is_active 更新字段。
        db: 数据库会话。

    返回:
        更新后的 ChunkResponse；不存在时 404。
    """
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
    """切换知识块启用/禁用状态。

    参数:
        chunk_id: 知识块 ID。
        is_active: 目标启用状态。
        db: 数据库会话。

    返回:
        更新后的 ChunkResponse。
    """
    service = ChunkService(db)
    return await service.toggle_status(chunk_id, is_active)


@router.post("/api/knowledge-bases/{kb_id}/search", response_model=SearchResponse)
async def search_knowledge(
    kb_id: str,
    data: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """知识检索测试（Hybrid 检索，不经过 LLM）。

    参数:
        kb_id: 知识库 ID。
        data: 查询文本与 top_k。
        db: 数据库会话。

    返回:
        SearchResponse 含排序后的检索项。
    """
    service = ChunkService(db)
    items = await service.search(kb_id, data.query, data.top_k)
    return SearchResponse(items=items, query=data.query)
