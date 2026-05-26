"""知识冲突 API — Phase 1.4"""

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
    svc = ConflictService(db)
    return await svc.list_pending(kb_id, status=status)


@router.post("/{conflict_id}/resolve")
async def resolve_conflict(
    kb_id: str,
    conflict_id: str,
    body: ConflictResolveRequest,
    db: AsyncSession = Depends(get_db),
):
    svc = ConflictService(db)
    try:
        return await svc.resolve(kb_id, conflict_id, body.resolution)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
