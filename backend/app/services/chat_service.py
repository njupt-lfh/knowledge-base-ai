"""对话服务"""

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.conversation import Conversation, Message
from ..schemas.chat import ConversationResponse, MessageResponse, ShareResponse
from ..utils.kb_id import KbIdResolver
from .conversation_extract_service import ConversationExtractService
from .gap_service import GapService
from .rag_service import RAGService

DEFAULT_CONV_TITLE = "新对话"
MAX_CONV_TITLE_LEN = 80


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.rag_svc = RAGService()

    async def create_conversation(self, kb_id: str) -> ConversationResponse:
        canonical = await KbIdResolver(self.db).resolve(kb_id)
        conv = Conversation(knowledge_base_id=canonical, title="新对话")
        self.db.add(conv)
        await self.db.commit()
        await self.db.refresh(conv)
        return ConversationResponse.model_validate(conv)

    async def list_conversations(
        self, kb_id: str, limit: int = 50, offset: int = 0
    ) -> list[ConversationResponse]:
        resolver = KbIdResolver(self.db)
        canonical = await resolver.resolve(kb_id)
        legacy = resolver.legacy_prefix(canonical)
        kb_ids = [canonical] if legacy == canonical else [canonical, legacy]
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.knowledge_base_id.in_(kb_ids))
            .order_by(Conversation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        convs = list(result.scalars().all())
        updated = False
        for conv in convs:
            if await self._maybe_set_conversation_title(conv):
                updated = True
        if updated:
            await self.db.commit()
            for conv in convs:
                await self.db.refresh(conv)
        return [ConversationResponse.model_validate(c) for c in convs]

    async def get_messages(self, conv_id: str) -> list[MessageResponse]:
        result = await self.db.execute(
            select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at)
        )
        return [MessageResponse.model_validate(m) for m in result.scalars().all()]

    async def delete_conversation(self, conv_id: str) -> bool:
        conv = await self.db.get(Conversation, conv_id)
        if not conv:
            return False
        await self.db.delete(conv)
        await self.db.commit()
        return True

    async def chat_stream(self, conv_id: str, message: str):
        """SSE 流式对话（Mock 或真实 RAG）"""
        # 获取对话关联的知识库
        conv = await self.db.get(Conversation, conv_id)
        kb_id = conv.knowledge_base_id if conv else ""

        # 先获取历史消息（不包含当前用户消息）
        history_result = await self.db.execute(
            select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at)
        )
        history = [{"role": m.role, "content": m.content} for m in history_result.scalars().all()]

        # 保存用户消息（在历史查询之后）
        user_msg = Message(conversation_id=conv_id, role="user", content=message)
        self.db.add(user_msg)
        await self.db.commit()

        if conv:
            await self._maybe_set_conversation_title(conv, message)
            await self.db.commit()
            await self.db.refresh(conv)

        # 收集完整回复与来源（含 Agent CRAG 判定，供补全任务去重）
        full_answer = ""
        sources_data = []
        crag_sufficient = False
        crag_refused = False

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
                        elif parsed.get("type") == "agent_meta":
                            crag_sufficient = bool(parsed.get("sufficient"))
                            crag_refused = bool(parsed.get("refused"))
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
                await gap_svc.process_after_chat(
                    kb_id=kb_id,
                    query=message,
                    answer=full_answer,
                    sources=sources_data or [],
                    conversation_id=conv_id,
                    message_id=assistant_msg.id,
                    crag_sufficient=crag_sufficient,
                    crag_refused=crag_refused,
                )
            except Exception:
                pass

    async def _maybe_set_conversation_title(
        self, conv: Conversation, first_question: str | None = None
    ) -> bool:
        if conv.title and conv.title != DEFAULT_CONV_TITLE:
            return False
        text = (first_question or "").strip()
        if not text:
            row = (
                await self.db.execute(
                    select(Message.content)
                    .where(Message.conversation_id == conv.id, Message.role == "user")
                    .order_by(Message.created_at)
                    .limit(1)
                )
            ).scalar_one_or_none()
            text = (row or "").strip()
        if not text:
            return False
        conv.title = text.replace("\n", " ")[:MAX_CONV_TITLE_LEN]
        return True

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

    async def extract_knowledge(self, conv_id: str) -> dict:
        """手动提炼最近一轮对话 → 结构化 Gap（含 source_ref）。"""
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at.desc())
            .limit(2)
        )
        recent = list(result.scalars().all())
        if len(recent) < 2:
            return {"has_knowledge": False, "kb_id": None}

        conv = await self.db.get(Conversation, conv_id)
        if not conv:
            return {"has_knowledge": False, "kb_id": None}

        user_msg = recent[1] if recent[1].role == "user" else recent[0]
        assistant_msg = recent[0] if recent[0].role == "assistant" else recent[1]

        gap_svc = GapService(self.db)
        gap_type = gap_svc.classify_gap(
            user_msg.content,
            conv.knowledge_base_id,
            [],
            user_message=user_msg.content,
        )

        if gap_type == "KNOWLEDGE_ABSENT":
            gap = await gap_svc.create_gap(
                kb_id=conv.knowledge_base_id,
                query=user_msg.content,
                gap_type="KNOWLEDGE_ABSENT",
                conversation_id=conv_id,
                source_ref=user_msg.content[:500],
            )
            return {
                "has_knowledge": True,
                "kb_id": conv.knowledge_base_id,
                "gap_id": gap.id,
                "gap_type": "KNOWLEDGE_ABSENT",
                "manual_required": True,
                "title": user_msg.content[:60],
                "content": None,
                "source_ref": user_msg.content[:200],
                "tags": [],
                "entities": [],
            }

        if gap_type not in ("USER_PROVIDED", "USER_CORRECTION"):
            gap_type = "USER_PROVIDED"

        extracted = await ConversationExtractService().extract_from_turn(
            user_msg.content,
            assistant_msg.content,
            hint_gap_type=gap_type,
        )
        if not extracted:
            return {"has_knowledge": False, "kb_id": conv.knowledge_base_id}

        gap = await gap_svc.create_gap(
            kb_id=conv.knowledge_base_id,
            query=user_msg.content,
            gap_type=extracted["gap_type"],
            conversation_id=conv_id,
            source_ref=extracted["source_ref"],
            suggested_content=ConversationExtractService.pack_suggested(extracted),
            confidence=0.9,
        )
        return {
            "has_knowledge": True,
            "kb_id": conv.knowledge_base_id,
            "gap_id": gap.id,
            "gap_type": extracted["gap_type"],
            "manual_required": False,
            "title": extracted.get("title"),
            "content": extracted.get("content"),
            "source_ref": extracted.get("source_ref"),
            "tags": extracted.get("tags") or [],
            "entities": extracted.get("entities") or [],
        }

    async def get_by_share_token(self, share_token: str) -> ConversationResponse | None:
        result = await self.db.execute(
            select(Conversation).where(Conversation.share_token == share_token)
        )
        conv = result.scalar_one_or_none()
        return ConversationResponse.model_validate(conv) if conv else None
