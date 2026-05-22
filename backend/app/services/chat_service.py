"""对话服务"""

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..models.conversation import Conversation, Message
from ..schemas.chat import ConversationResponse, MessageResponse, ShareResponse


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_conversation(self, kb_id: str) -> ConversationResponse:
        conv = Conversation(
            knowledge_base_id=kb_id,
            title="新对话",
        )
        self.db.add(conv)
        await self.db.commit()
        await self.db.refresh(conv)
        return ConversationResponse.model_validate(conv)

    async def list_conversations(self, kb_id: str) -> list[ConversationResponse]:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.knowledge_base_id == kb_id)
            .order_by(Conversation.created_at.desc())
        )
        return [ConversationResponse.model_validate(c) for c in result.scalars().all()]

    async def get_messages(self, conv_id: str) -> list[MessageResponse]:
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at)
        )
        return [MessageResponse.model_validate(m) for m in result.scalars().all()]

    async def chat_stream(self, conv_id: str, message: str):
        """SSE 流式对话（Mock 模式）"""
        # 保存用户消息
        user_msg = Message(
            conversation_id=conv_id,
            role="user",
            content=message,
        )
        self.db.add(user_msg)
        await self.db.commit()

        # 模拟流式返回
        mock_reply = f"您好！您的问题是：「{message}」。\n\n目前系统处于 Mock 模式（LLM_MOCK_MODE=true），AI 对话功能将在接入火山引擎 API 后正式启用。\n\n请确保以下配置正确：\n- .env 中 VOLCENGINE_API_KEY 已填写\n- LLM_MOCK_MODE=false"

        yield "data: {\"type\": \"thinking\", \"content\": \"正在检索相关知识...\"}\n\n"

        # 逐字输出
        for char in mock_reply:
            yield f"data: {{\"type\": \"text\", \"content\": {json.dumps(char)}}}\n\n"

        yield "data: {\"type\": \"sources\", \"sources\": []}\n\n"
        yield "data: {\"type\": \"done\"}\n\n"

        # 保存助手消息
        assistant_msg = Message(
            conversation_id=conv_id,
            role="assistant",
            content=mock_reply,
        )
        self.db.add(assistant_msg)
        await self.db.commit()

    async def create_share(self, conv_id: str) -> ShareResponse:
        conv = await self.db.get(Conversation, conv_id)
        if not conv:
            conv.share_token = str(uuid.uuid4())
        share_token = conv.share_token or str(uuid.uuid4())
        if not conv.share_token:
            conv.share_token = share_token
            await self.db.commit()
        return ShareResponse(
            share_token=share_token,
            share_url=f"/share/{share_token}",
        )

    async def get_by_share_token(self, share_token: str) -> ConversationResponse | None:
        result = await self.db.execute(
            select(Conversation).where(Conversation.share_token == share_token)
        )
        conv = result.scalar_one_or_none()
        return ConversationResponse.model_validate(conv) if conv else None
