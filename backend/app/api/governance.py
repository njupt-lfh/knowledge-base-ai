"""知识库治理 API 路由（Phase 1.3 + Phase 3 治理闭环）。

提供扫描、建议列表、状态机操作（approve/dismiss/execute/verify）与审计日志。
"""

import uuid

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
    """扫描知识库并返回治理建议（实时扫描，不持久化）。"""
    svc = GovernanceService(db)
    return await svc.scan_suggestions(kb_id, scan_duplicates=scan_duplicates)


@router.post("/suggestions/scan")
async def scan_and_persist_suggestions(
    kb_id: str,
    scan_duplicates: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """扫描 + 持久化治理建议（Phase 3 治理闭环）。"""
    svc = GovernanceService(db)
    result = await svc.scan_suggestions(kb_id, scan_duplicates=scan_duplicates)
    scan_id = str(uuid.uuid4())
    count = await svc.persist_suggestions(kb_id, result["suggestions"], scan_id=scan_id)
    return {"scan_id": scan_id, "new_suggestions": count, **result}


@router.get("/suggestions/persisted/counts", name="persisted_suggestion_counts")
async def persisted_suggestion_counts(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
):
    """各状态治理建议数量（Tab 角标用，一次查询不受分页影响）。"""
    svc = GovernanceService(db)
    return await svc.suggestion_status_counts(kb_id)


@router.get("/chunk-refs")
async def resolve_governance_chunk_refs(
    kb_id: str,
    ids: str = Query("", description="逗号分隔的 chunk ID"),
    db: AsyncSession = Depends(get_db),
):
    """批量解析治理建议关联 chunk 的文档名与段落序号。"""
    chunk_ids = [x.strip() for x in ids.split(",") if x.strip()]
    svc = GovernanceService(db)
    return await svc.resolve_chunk_refs(kb_id, chunk_ids)


@router.get("/suggestions/persisted")
async def list_persisted_suggestions(
    kb_id: str,
    status: str | None = Query(None),
    suggestion_type: str | None = Query(None, alias="type"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """列出已持久化的治理建议（支持状态/类型过滤、分页与总数）。"""
    svc = GovernanceService(db)
    return await svc.list_suggestions(
        kb_id,
        status=status,
        suggestion_type=suggestion_type,
        offset=offset,
        limit=limit,
    )


@router.post("/suggestions/{suggestion_id}/approve")
async def approve_suggestion(
    kb_id: str,
    suggestion_id: str,
    db: AsyncSession = Depends(get_db),
):
    """批准治理建议（pending → approved）。"""
    svc = GovernanceService(db)
    row = await svc.approve_suggestion(suggestion_id)
    if not row or row.kb_id != kb_id:
        raise HTTPException(status_code=404, detail="suggestion not found or not pending")
    return {"status": "approved", "suggestion_id": suggestion_id}


@router.post("/suggestions/{suggestion_id}/dismiss")
async def dismiss_suggestion(
    kb_id: str,
    suggestion_id: str,
    reason: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    """驳回治理建议（pending → dismissed）。"""
    svc = GovernanceService(db)
    row = await svc.dismiss_suggestion(suggestion_id, reason=reason)
    if not row or row.kb_id != kb_id:
        raise HTTPException(status_code=404, detail="suggestion not found or not pending")
    return {"status": "dismissed", "suggestion_id": suggestion_id}


@router.post("/suggestions/{suggestion_id}/execute")
async def execute_suggestion(
    kb_id: str,
    suggestion_id: str,
    db: AsyncSession = Depends(get_db),
):
    """执行已批准的治理建议（approved → executed，同步 Chroma/FTS）。"""
    svc = GovernanceService(db)
    result = await svc.execute_suggestion(suggestion_id)
    if result is None:
        raise HTTPException(status_code=404, detail="suggestion not found or not approved")
    return {"status": "executed", "suggestion_id": suggestion_id, "result": result}


@router.post("/suggestions/{suggestion_id}/verify")
async def verify_suggestion(
    kb_id: str,
    suggestion_id: str,
    db: AsyncSession = Depends(get_db),
):
    """验证执行结果（executed → verified）。"""
    svc = GovernanceService(db)
    row = await svc.verify_suggestion(suggestion_id)
    if not row or row.kb_id != kb_id:
        raise HTTPException(status_code=404, detail="suggestion not found or not executed")
    return {"status": "verified", "suggestion_id": suggestion_id}


@router.post("/actions")
async def apply_governance_action(
    kb_id: str,
    body: GovernanceActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """对指定 chunk 批量执行治理动作。"""
    svc = GovernanceService(db)
    try:
        return await svc.apply_action(kb_id, body.action, body.chunk_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/suggestions/{suggestion_id}/rollback")
async def rollback_suggestion(
    kb_id: str,
    suggestion_id: str,
    db: AsyncSession = Depends(get_db),
):
    """回退建议（approved → pending 或 executed → approved）。"""
    svc = GovernanceService(db)
    result = await svc.rollback_suggestion(suggestion_id)
    if result is None:
        raise HTTPException(
            status_code=400,
            detail="不可回退（仅 approved 或 executed 状态可回退）",
        )
    return result


@router.get("/audit-log")
async def get_audit_log(
    kb_id: str,
    action: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """查询治理审计日志（可按动作筛选）。"""
    svc = GovernanceService(db)
    return await svc.get_audit_log(kb_id, action=action, limit=limit)
