"""知识缺口队列 API"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..schemas.gap import GapCreateRequest, GapIngestRequest, GapResponse, GapStatusUpdate
from ..services.gap_service import GapService
from ..services.rag_service import RAGService

router = APIRouter(prefix="/api/knowledge-bases/{kb_id}/gaps", tags=["gaps"])


@router.get("", response_model=list[GapResponse])
async def list_gaps(
    kb_id: str,
    gap_type: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    svc = GapService(db)
    gaps = await svc.list_gaps(kb_id, gap_type=gap_type, status=status, limit=limit)
    return [GapResponse.model_validate(g) for g in gaps]


@router.post("", response_model=GapResponse, status_code=201)
async def create_gap(
    kb_id: str,
    body: GapCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    svc = GapService(db)
    rag = RAGService()
    sources = await rag.retrieve(kb_id, body.query, top_k=5, db=db)
    gap_type = body.gap_type or svc.classify_gap(
        body.query,
        kb_id,
        sources,
        correction_text=body.correction_text,
        user_message=body.query,
    )
    gap = await svc.create_gap(
        kb_id=kb_id,
        query=body.query,
        gap_type=gap_type,
        source_ref=body.source_ref,
        retrieval_result=sources,
    )
    return GapResponse.model_validate(gap)


@router.post("/{gap_id}/ingest")
async def ingest_gap(
    kb_id: str,
    gap_id: str,
    body: GapIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """批准入库：仅 USER_PROVIDED/USER_CORRECTION（需 source_ref）；KNOWLEDGE_ABSENT 仅人工正文。"""
    svc = GapService(db)
    try:
        return await svc.ingest_gap(
            kb_id,
            gap_id,
            manual_content=body.manual_content,
            manual_title=body.manual_title,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.patch("/{gap_id}/status", response_model=GapResponse)
async def update_gap_status(
    kb_id: str,
    gap_id: str,
    body: GapStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    svc = GapService(db)
    gap = await svc.update_status(gap_id, body.status)
    if not gap or gap.kb_id != kb_id:
        raise HTTPException(status_code=404, detail="gap not found")
    return GapResponse.model_validate(gap)
