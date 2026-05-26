"""知识库治理 API — Phase 1.3"""

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
    svc = GovernanceService(db)
    return await svc.scan_suggestions(kb_id, scan_duplicates=scan_duplicates)


@router.post("/actions")
async def apply_governance_action(
    kb_id: str,
    body: GovernanceActionRequest,
    db: AsyncSession = Depends(get_db),
):
    svc = GovernanceService(db)
    try:
        return await svc.apply_action(kb_id, body.action, body.chunk_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
