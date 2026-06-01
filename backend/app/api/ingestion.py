"""入库预检 API 路由（Phase 1.4）。

在正式写入前检测内容与已有 chunk 的重复或语义冲突，
委托 `IngestionGateService` 减少脏数据入库。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..schemas.conflict import IngestPrecheckRequest, IngestPrecheckResponse
from ..services.ingestion_gate_service import IngestionGateService

router = APIRouter(prefix="/api/knowledge-bases/{kb_id}/ingestion", tags=["ingestion"])


@router.post("/precheck", response_model=IngestPrecheckResponse)
async def precheck_ingestion(
    kb_id: str,
    body: IngestPrecheckRequest,
    db: AsyncSession = Depends(get_db),
):
    """对待入库正文执行重复/冲突预检。

    参数:
        kb_id: 知识库 ID。
        body: 待检测 content。
        db: 数据库会话。

    返回:
        IngestPrecheckResponse 含 status、相似度及提示 message。
    """
    gate = IngestionGateService(db)
    result = await gate.check_content(kb_id, body.content)
    msg = None
    if result.status == "duplicate":
        msg = f"与已有知识块高度相似（{result.similarity}），建议合并"
    elif result.status == "conflict":
        msg = "检测到与已有知识可能语义冲突，需人工裁决"
    return IngestPrecheckResponse(
        status=result.status,
        duplicate_of=result.duplicate_of,
        similarity=result.similarity,
        llm_calls=result.llm_calls,
        message=msg,
    )
