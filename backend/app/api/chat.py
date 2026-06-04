"""对话 API 路由。

提供会话 CRUD、SSE 流式聊天、分享链接及对话知识提炼端点，
委托 `ChatService` 处理 RAG 检索与 LLM 生成逻辑。
"""

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


@router.post(
    "/api/knowledge-bases/{kb_id}/chat", response_model=ConversationResponse, status_code=201
)
async def create_conversation(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
):
    """创建新对话。

    参数:
        kb_id: 知识库 ID，绑定后续检索范围。
        db: 数据库会话。

    返回:
        新建的 ConversationResponse。
    """
    service = ChatService(db)
    return await service.create_conversation(kb_id)


@router.get("/api/knowledge-bases/{kb_id}/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    kb_id: str,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """获取对话列表（分页）。

    参数:
        kb_id: 知识库 ID。
        limit: 每页条数。
        offset: 偏移量。
        db: 数据库会话。

    返回:
        ConversationResponse 列表。
    """
    service = ChatService(db)
    return await service.list_conversations(kb_id, limit=limit, offset=offset)


@router.get("/api/conversations/{conv_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    conv_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取对话全部消息。

    参数:
        conv_id: 对话 ID。
        db: 数据库会话。

    返回:
        MessageResponse 列表。
    """
    service = ChatService(db)
    return await service.get_messages(conv_id)


@router.post("/api/conversations/{conv_id}/chat")
async def send_message(
    conv_id: str,
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """发送消息（SSE 流式响应）。

    参数:
        conv_id: 对话 ID。
        data: 含 message 与 knowledge_base_id 的请求体。
        db: 数据库会话。

    返回:
        text/event-stream 流式 HTTP 响应。
    """
    service = ChatService(db)
    return StreamingResponse(
        service.chat_stream(conv_id, data.message, fast_mode=data.fast_mode),
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
    """生成分享链接。

    参数:
        conv_id: 对话 ID。
        db: 数据库会话。

    返回:
        share_token 与 share_url。
    """
    service = ChatService(db)
    return await service.create_share(conv_id)


@router.get("/api/share/{share_token}", response_model=ConversationResponse)
async def get_shared_conversation(
    share_token: str,
    db: AsyncSession = Depends(get_db),
):
    """通过分享 token 获取只读对话元数据。

    参数:
        share_token: 分享令牌。
        db: 数据库会话。

    返回:
        ConversationResponse；无效 token 时 404。
    """
    service = ChatService(db)
    conv = await service.get_by_share_token(share_token)
    if not conv:
        raise HTTPException(status_code=404, detail="分享链接无效")
    return conv


@router.delete("/api/conversations/{conv_id}")
async def delete_conversation(
    conv_id: str,
    db: AsyncSession = Depends(get_db),
):
    """删除对话及其所有消息。

    参数:
        conv_id: 对话 ID。
        db: 数据库会话。

    返回:
        成功时 {"detail": "ok"}；不存在时 404。
    """
    service = ChatService(db)
    ok = await service.delete_conversation(conv_id)
    if not ok:
        raise HTTPException(status_code=404, detail="对话不存在")
    return {"detail": "ok"}


@router.post("/api/conversations/{conv_id}/extract-knowledge")
async def extract_knowledge(
    conv_id: str,
    db: AsyncSession = Depends(get_db),
):
    """从最近一轮对话结构化提炼知识（Phase 1.5）。

    参数:
        conv_id: 对话 ID。
        db: 数据库会话。

    返回:
        提炼结果字典（由 ChatService 定义）。
    """
    service = ChatService(db)
    return await service.extract_knowledge(conv_id)
