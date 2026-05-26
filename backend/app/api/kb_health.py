"""知识库健康度 API"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services.health_service import knowledge_base_health

router = APIRouter(tags=["health"])


@router.get("/api/knowledge-bases/{kb_id}/health")
async def get_kb_health(kb_id: str, db: AsyncSession = Depends(get_db)):
    return await knowledge_base_health(db, kb_id)
