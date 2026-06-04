"""答案一致性审核队列 API（Phase 2）。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..schemas.answer_review import (
    AnswerReviewCreateRequest,
    AnswerReviewResponse,
    AnswerReviewStatusUpdate,
)
from ..services.answer_review_service import AnswerReviewService
from ..utils.kb_id import KbIdResolver

router = APIRouter(
    prefix="/api/knowledge-bases/{kb_id}/answer-reviews",
    tags=["answer-reviews"],
)


@router.get("", response_model=list[AnswerReviewResponse])
async def list_answer_reviews(
    kb_id: str,
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """列出待审核的双路径答案工单。"""
    try:
        await KbIdResolver(db).resolve(kb_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    svc = AnswerReviewService(db)
    rows = await svc.list_reviews(kb_id, status=status, limit=limit)
    return [AnswerReviewResponse.model_validate(r) for r in rows]


@router.post("", response_model=AnswerReviewResponse, status_code=201)
async def create_answer_review(
    kb_id: str,
    body: AnswerReviewCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """手动创建审核工单（管理/测试用）。"""
    svc = AnswerReviewService(db)
    try:
        row = await svc.create_manual(
            kb_id,
            query=body.query,
            answer_a=body.answer_a,
            answer_b=body.answer_b,
            verdict=body.verdict,
            reason=body.reason,
            route=body.route,
            ctx_hash=body.ctx_hash,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return AnswerReviewResponse.model_validate(row)


@router.patch("/{review_id}/status", response_model=AnswerReviewResponse)
async def update_answer_review_status(
    kb_id: str,
    review_id: str,
    body: AnswerReviewStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新审核工单状态。"""
    resolver = KbIdResolver(db)
    try:
        canonical = await resolver.resolve(kb_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    svc = AnswerReviewService(db)
    row = await svc.update_status(
        review_id,
        status=body.status,
        assignee=body.assignee,
    )
    if not row or row.kb_id != canonical:
        raise HTTPException(status_code=404, detail="review not found")
    return AnswerReviewResponse.model_validate(row)
