"""对话服务"""

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.conversation import Conversation, Message
from ..schemas.chat import ConversationResponse, MessageResponse, ShareResponse
from .gap_service import GapService
from .rag_service import RAGService


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.rag_svc = RAGService()

    async def create_conversation(self, kb_id: str) -> ConversationResponse:
        conv = Conversation(knowledge_base_id=kb_id, title="新对话")
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
        """SSE 流式对话（Mock 或真实 RAG）"""
        # 获取对话关联的知识库
        conv = await self.db.get(Conversation, conv_id)
        kb_id = conv.knowledge_base_id if conv else ""

        # 先获取历史消息（不包含当前用户消息）
        history_result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at)
        )
        history = [
            {"role": m.role, "content": m.content}
            for m in history_result.scalars().all()
        ]

        # 保存用户消息（在历史查询之后）
        user_msg = Message(conversation_id=conv_id, role="user", content=message)
        self.db.add(user_msg)
        await self.db.commit()

        # 收集完整回复与来源
        full_answer = ""
        sources_data = []

        if settings.LLM_MOCK_MODE:
            mock_reply = f"Mock 模式: 您的问题是「{message}」。请在 .env 设置 LLM_MOCK_MODE=false"
            for char in mock_reply:
                full_answer += char
                yield f"data: {json.dumps({'type': 'text', 'content': char})}\n\n"
            yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        else:
            try:
                async for event_str in self.rag_svc.generate(kb_id, message, history, db=self.db):
                    yield event_str
                    try:
                        parsed = json.loads(event_str.replace("data: ", ""))
                        if parsed.get("type") == "text":
                            full_answer += parsed.get("content", "")
                        elif parsed.get("type") == "sources":
                            sources_data = parsed.get("sources", [])
                    except Exception:
                        pass
            except Exception as e:
                error_msg = f"AI 服务调用失败: {str(e)}"
                full_answer = error_msg
                yield f"data: {json.dumps({'type': 'text', 'content': error_msg})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

        # 保存助手消息（含来源引用）
        assistant_msg = Message(
            conversation_id=conv_id,
            role="assistant",
            content=full_answer,
            sources=sources_data if sources_data else None,
        )
        self.db.add(assistant_msg)
        await self.db.commit()
        await self.db.refresh(assistant_msg)

        if kb_id and not settings.LLM_MOCK_MODE:
            try:
                gap_svc = GapService(self.db)
                await gap_svc.maybe_enqueue_from_chat(
                    kb_id=kb_id,
                    query=message,
                    answer=full_answer,
                    sources=sources_data or [],
                    conversation_id=conv_id,
                    message_id=assistant_msg.id,
                )
            except Exception:
                pass

    async def create_share(self, conv_id: str) -> ShareResponse:
        conv = await self.db.get(Conversation, conv_id)
        if not conv.share_token:
            conv.share_token = str(uuid.uuid4())
            await self.db.commit()
            await self.db.refresh(conv)
        return ShareResponse(
            share_token=conv.share_token,
            share_url=f"/share/{conv.share_token}",
        )

    async def get_by_share_token(self, share_token: str) -> ConversationResponse | None:
        result = await self.db.execute(
            select(Conversation).where(Conversation.share_token == share_token)
        )
        conv = result.scalar_one_or_none()
        return ConversationResponse.model_validate(conv) if conv else None
