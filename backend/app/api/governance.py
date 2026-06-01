"""知识库治理 API 路由（Phase 1.3）。

提供重复/低质 chunk 扫描建议与批量治理动作（归档、停用、FAQ 加权、合并），
委托 `GovernanceService` 执行。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..schemas.governance import GovernanceActionRequest
from ..services.governance_service import GovernanceService

router = APIRouter(prefix="/api/knowledge-bases/{kb_id}/governance", tags=["governance"])


@router.get("/suggestions")
async def list_governance_suggestions(
    kb_id: str,
    scan_duplicates: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """扫描知识库并返回治理建议（重复、低质等）。

    参数:
        kb_id: 知识库 ID。
        scan_duplicates: 是否扫描重复 chunk。
        db: 数据库会话。

    返回:
        建议列表（由 GovernanceService 定义结构）。
    """
    svc = GovernanceService(db)
    return await svc.scan_suggestions(kb_id, scan_duplicates=scan_duplicates)


@router.post("/actions")
async def apply_governance_action(
    kb_id: str,
    body: GovernanceActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """对指定 chunk 批量执行治理动作。

    参数:
        kb_id: 知识库 ID。
        body: action 与 chunk_ids 列表。
        db: 数据库会话。

    返回:
        动作执行结果；非法 action 时 400。
    """
    svc = GovernanceService(db)
    try:
        return await svc.apply_action(kb_id, body.action, body.chunk_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
