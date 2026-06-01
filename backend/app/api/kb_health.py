"""知识库健康度 API 路由。

暴露单库健康评分与诊断指标，委托 `health_service.knowledge_base_health`
聚合文档状态、缺口、冲突等维度。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services.health_service import knowledge_base_health

router = APIRouter(tags=["health"])


@router.get("/api/knowledge-bases/{kb_id}/health")
async def get_kb_health(kb_id: str, db: AsyncSession = Depends(get_db)):
    """获取指定知识库的健康度报告。

    参数:
        kb_id: 知识库 ID。
        db: 数据库会话。

    返回:
        健康度指标字典（由 health_service 定义）。
    """
    return await knowledge_base_health(db, kb_id)
