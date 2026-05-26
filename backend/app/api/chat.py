"""对话 API 路由"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..schemas.chat import (
    ChatRequest,
    ConversationResponse,
    MessageResponse,
    ShareResponse,
)
from ..services.chat_service import ChatService

router = APIRouter(tags=["对话"])


@router.post("/api/knowledge-bases/{kb_id}/chat", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
):
    """创建新对话"""
    service = ChatService(db)
    return await service.create_conversation(kb_id)


@router.get("/api/knowledge-bases/{kb_id}/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取对话列表"""
    service = ChatService(db)
    return await service.list_conversations(kb_id)


@router.get("/api/conversations/{conv_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    conv_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取对话消息"""
    service = ChatService(db)
    return await service.get_messages(conv_id)


@router.post("/api/conversations/{conv_id}/chat")
async def send_message(
    conv_id: str,
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """发送消息（SSE 流式响应）"""
    service = ChatService(db)
    return StreamingResponse(
        service.chat_stream(conv_id, data.message),
        media_type="text/event-stream;charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/conversations/{conv_id}/share", response_model=ShareResponse)
async def share_conversation(
    conv_id: str,
    db: AsyncSession = Depends(get_db),
):
    """生成分享链接"""
    service = ChatService(db)
    return await service.create_share(conv_id)


@router.get("/api/share/{share_token}", response_model=ConversationResponse)
async def get_shared_conversation(
    share_token: str,
    db: AsyncSession = Depends(get_db),
):
    """获取分享对话"""
    service = ChatService(db)
    conv = await service.get_by_share_token(share_token)
    if not conv:
        raise HTTPException(status_code=404, detail="分享链接无效")
    return conv


@router.post("/api/conversations/{conv_id}/extract-knowledge")
async def extract_knowledge(
    conv_id: str,
    db: AsyncSession = Depends(get_db),
):
    """从最近一轮对话结构化提炼知识（Phase 1.5）"""
    service = ChatService(db)
    return await service.extract_knowledge(conv_id)
