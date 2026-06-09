"""知识缺口队列 API 路由（Phase 1）。

提供缺口列表、创建、批准入库与状态更新端点，
结合 RAG 检索结果自动分类缺口类型。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.knowledge_gap import KnowledgeGap
from ..schemas.gap import (
    GapAuditLogResponse,
    GapBatchDeleteRequest,
    GapCreateRequest,
    GapFollowUpRequest,
    GapIngestRequest,
    GapResponse,
    GapStatusUpdate,
)
from ..services.gap_service import GapService
from ..services.rag_service import RAGService
from ..utils.kb_id import KbIdResolver

router = APIRouter(prefix="/api/knowledge-bases/{kb_id}/gaps", tags=["gaps"])


@router.get("", response_model=list[GapResponse])
async def list_gaps(
    kb_id: str,
    gap_type: str | None = Query(None),
    status: str | None = Query(None),
    queue: str = Query("pending", description="pending|completed|all"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """列出知识库缺口工单，可按类型、状态与队列视图过滤。

    参数:
        kb_id: 知识库 ID（支持前缀解析）。
        gap_type: 可选缺口类型过滤。
        status: 可选状态过滤。
        queue: pending 待处理 / completed 已完成。
        limit: 最大返回条数。
        db: 数据库会话。

    返回:
        GapResponse 列表；知识库不存在时 404。
    """
    if queue not in ("pending", "completed", "all"):
        raise HTTPException(status_code=400, detail="invalid queue")
    svc = GapService(db)
    try:
        gaps = await svc.list_gaps(
            kb_id,
            gap_type=gap_type,
            status=status,
            queue=queue,
            limit=limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return [GapResponse.model_validate(g) for g in gaps]


@router.post("", response_model=GapResponse, status_code=201)
async def create_gap(
    kb_id: str,
    body: GapCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """创建缺口工单：先检索再自动或指定 gap_type。

    参数:
        kb_id: 知识库 ID。
        body: 查询文本及可选类型、来源、纠错文本。
        db: 数据库会话。

    返回:
        新建的 GapResponse。
    """
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
    """批准缺口入库：仅 USER_PROVIDED/USER_CORRECTION（需 source_ref）；KNOWLEDGE_ABSENT 仅人工正文。

    参数:
        kb_id: 知识库 ID。
        gap_id: 缺口工单 ID。
        body: 可选人工标题与正文覆盖。
        db: 数据库会话。

    返回:
        入库结果字典；业务校验失败时 400。
    """
    svc = GapService(db)
    try:
        result = await svc.ingest_gap(
            kb_id,
            gap_id,
            manual_content=body.manual_content,
            manual_title=body.manual_title,
        )
        return JSONResponse(status_code=202, content=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.patch("/{gap_id}/status", response_model=GapResponse)
async def update_gap_status(
    kb_id: str,
    gap_id: str,
    body: GapStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新缺口工单状态。

    参数:
        kb_id: 知识库 ID（用于校验 gap 归属，含历史前缀）。
        gap_id: 缺口 ID。
        body: 新 status。
        db: 数据库会话。

    返回:
        更新后的 GapResponse；不存在或不归属该库时 404。
    """
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


@router.delete("/batch")
async def batch_delete_gaps(
    kb_id: str,
    body: GapBatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """批量删除缺口工单（不删除已入库文档）。"""
    svc = GapService(db)
    try:
        return await svc.delete_gaps_batch(kb_id, body.gap_ids)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/{gap_id}", status_code=204)
async def delete_gap(
    kb_id: str,
    gap_id: str,
    db: AsyncSession = Depends(get_db),
):
    """删除缺口工单。

    参数:
        kb_id: 知识库 ID（用于校验 gap 归属）。
        gap_id: 缺口 ID。
        db: 数据库会话。

    返回:
        204 No Content；不存在或不归属 404。
    """
    svc = GapService(db)
    resolver = KbIdResolver(db)
    try:
        canonical = await resolver.resolve(kb_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    gap = await db.get(KnowledgeGap, gap_id)
    if not gap or not resolver.gap_kb_matches(gap.kb_id, canonical):
        raise HTTPException(status_code=404, detail="gap not found")
    if gap.status == "processing":
        raise HTTPException(status_code=400, detail="processing gap cannot be deleted")
    try:
        await svc.delete_gap(gap_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return None


@router.get("/{gap_id}/audit-log", response_model=list[GapAuditLogResponse])
async def get_gap_audit_log(
    kb_id: str,
    gap_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """获取单条 Gap 的处理记录。"""
    svc = GapService(db)
    try:
        rows = await svc.get_audit_log(kb_id, gap_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return [GapAuditLogResponse.model_validate(r) for r in rows]


@router.post("/{gap_id}/follow-up", response_model=GapResponse, status_code=201)
async def follow_up_gap(
    kb_id: str,
    gap_id: str,
    body: GapFollowUpRequest,
    db: AsyncSession = Depends(get_db),
):
    """基于已入库 Gap 创建续补任务。"""
    svc = GapService(db)
    try:
        gap = await svc.create_follow_up(
            kb_id,
            gap_id,
            correction_text=body.correction_text,
            source_ref=body.source_ref,
        )
    except ValueError as e:
        msg = str(e)
        code = 404 if "not found" in msg else 400
        raise HTTPException(status_code=code, detail=msg) from e
    return GapResponse.model_validate(gap)
