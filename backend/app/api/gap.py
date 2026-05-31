"""知识缺口队列 API"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..schemas.gap import GapCreateRequest, GapIngestRequest, GapResponse, GapStatusUpdate
from ..services.gap_service import GapService
from ..services.rag_service import RAGService
from ..utils.kb_id import KbIdResolver

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
    try:
        gaps = await svc.list_gaps(kb_id, gap_type=gap_type, status=status, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return [GapResponse.model_validate(g) for g in gaps]


@router.post("", response_model=GapResponse, status_code=201)
async def create_gap(
    kb_id: str,
    body: GapCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    svc = GapService(db)
    try:
        canonical = await KbIdResolver(db).resolve(kb_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    rag = RAGService()
    sources = await rag.retrieve(canonical, body.query, top_k=5, db=db)
    gap_type = body.gap_type or svc.classify_gap(
        body.query,
        canonical,
        sources,
        correction_text=body.correction_text,
        user_message=body.query,
    )
    gap = await svc.create_gap(
        kb_id=canonical,
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
    resolver = KbIdResolver(db)
    try:
        canonical = await resolver.resolve(kb_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    gap = await svc.update_status(gap_id, body.status)
    if not gap or not resolver.gap_kb_matches(gap.kb_id, canonical):
        raise HTTPException(status_code=404, detail="gap not found")
    return GapResponse.model_validate(gap)
