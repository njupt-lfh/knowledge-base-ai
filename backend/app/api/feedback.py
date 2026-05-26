from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..schemas.feedback import FeedbackCreate, FeedbackResponse
from ..services.feedback_service import FeedbackService

router = APIRouter(prefix="/api/knowledge-bases/{kb_id}/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse, status_code=201)
async def submit_feedback(
    kb_id: str,
    body: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
):
    svc = FeedbackService(db)
    try:
        row = await svc.create_feedback(
            kb_id,
            message_id=body.message_id,
            feedback_type=body.feedback_type,
            chunk_id=body.chunk_id,
            chunk_ids=body.chunk_ids,
            correction_text=body.correction_text,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return FeedbackResponse.model_validate(row)
