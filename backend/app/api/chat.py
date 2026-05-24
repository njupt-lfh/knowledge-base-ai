"""对话 API 路由"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
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
    """从最近一轮对话中提炼知识（T6.5）"""
    from ..models.conversation import Conversation, Message
    from sqlalchemy import select
    import httpx, json

    conv = await db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.desc())
        .limit(2)
    )
    recent = result.scalars().all()
    if len(recent) < 2:
        return {"has_knowledge": False}

    user_msg = recent[1] if recent[1].role == "user" else recent[0]
    assistant_msg = recent[0] if recent[0].role == "assistant" else recent[1]

    prompt = f"""判断以下对话是否包含值得存入知识库的新知识点。只返回JSON。

{{"has_knowledge": true/false, "title": "知识点标题", "content": "详细知识内容"}}

用户：{user_msg.content}
助手：{assistant_msg.content}"""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.VOLCENGINE_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.VOLCENGINE_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.VOLCENGINE_LLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.3,
                },
            )
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("\n", 1)[0]
            result = json.loads(content)
            result["kb_id"] = conv.knowledge_base_id
            return result
    except Exception:
        return {"has_knowledge": False}
