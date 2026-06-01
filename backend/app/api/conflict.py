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
    status: str | None = Query("pending"),
    db: AsyncSession = Depends(get_db),
):
    """列出知识库内指定状态的冲突记录。

    参数:
        kb_id: 知识库 ID。
        status: 冲突状态过滤，默认 pending。
        db: 数据库会话。

    返回:
        冲突列表（由 ConflictService 序列化）。
    """
    svc = ConflictService(db)
    return await svc.list_pending(kb_id, status=status)


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
