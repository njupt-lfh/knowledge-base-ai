"""知识冲突 API 路由（Phase 1.4）。

提供待裁决冲突列表与人工裁决端点，
委托 `ConflictService` 处理保留新/旧内容或驳回。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..schemas.conflict import ConflictResolveRequest
from ..services.conflict_service import ConflictService

router = APIRouter(prefix="/api/knowledge-bases/{kb_id}/conflicts", tags=["conflicts"])


@router.get("")
async def list_conflicts(
    kb_id: str,
    status: str = Query("pending", description="pending | history | 具体裁决状态"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """列出知识库内冲突记录（待裁决或裁决历史）。

    参数:
        kb_id: 知识库 ID。
        status: pending 待裁决；history 全部已裁决记录。
        limit: 返回条数上限。
        db: 数据库会话。

    返回:
        冲突列表（由 ConflictService 序列化）。
    """
    svc = ConflictService(db)
    return await svc.list_conflicts(kb_id, status=status, limit=limit)


@router.post("/{conflict_id}/resolve")
async def resolve_conflict(
    kb_id: str,
    conflict_id: str,
    body: ConflictResolveRequest,
    db: AsyncSession = Depends(get_db),
):
    """对单条冲突执行裁决。

    参数:
        kb_id: 知识库 ID。
        conflict_id: 冲突记录 ID。
        body: 含 resolution 的裁决请求。
        db: 数据库会话。

    返回:
        裁决结果；参数非法时 400。
    """
    svc = ConflictService(db)
    try:
        return await svc.resolve(kb_id, conflict_id, body.resolution)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{conflict_id}/rollback")
async def rollback_conflict(
    kb_id: str,
    conflict_id: str,
    db: AsyncSession = Depends(get_db),
):
    """回退已裁决冲突到待裁决队列。"""
    svc = ConflictService(db)
    try:
        return await svc.rollback(kb_id, conflict_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
