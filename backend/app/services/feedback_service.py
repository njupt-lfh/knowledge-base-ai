"""用户反馈服务 — 关联 message / chunk，dislike/correction 可触发 Gap，并更新质量分"""

import json

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chunk_feedback import FEEDBACK_TYPES, ChunkFeedback
from ..models.conversation import Message
from .gap_service import GapService
from .quality_service import QualityService


class FeedbackService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_feedback(
        self,
        kb_id: str,
        *,
        message_id: str,
        feedback_type: str,
        chunk_id: str | None = None,
        chunk_ids: list[str] | None = None,
        correction_text: str | None = None,
    ) -> ChunkFeedback:
        if feedback_type not in FEEDBACK_TYPES:
            raise ValueError(f"invalid feedback_type: {feedback_type}")

        msg = await self.db.get(Message, message_id)
        if not msg:
            raise ValueError("message not found")

        resolved_ids = await self._resolve_chunk_ids(msg, chunk_id, chunk_ids)
        primary_chunk = resolved_ids[0] if resolved_ids else chunk_id

        row = ChunkFeedback(
            kb_id=kb_id,
            message_id=message_id,
            chunk_id=primary_chunk,
            feedback_type=feedback_type,
            correction_text=correction_text,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)

        if resolved_ids:
            quality_svc = QualityService(self.db)
            await quality_svc.apply_feedback(resolved_ids, feedback_type)

        if feedback_type in ("dislike", "correction"):
            gap_svc = GapService(self.db)
            user_q = await self._find_user_query(msg.conversation_id, message_id)
            gap_type = "USER_CORRECTION" if feedback_type == "correction" else "RETRIEVAL_MISS"
            await gap_svc.create_gap(
                kb_id=kb_id,
                query=user_q or msg.content[:200],
                gap_type=gap_type,
                conversation_id=msg.conversation_id,
                message_id=message_id,
                source_ref=correction_text or f"feedback:{feedback_type}",
            )

        return row

    async def _find_user_query(self, conversation_id: str, assistant_message_id: str) -> str | None:
        from sqlalchemy import select

        from ..models.conversation import Message

        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        messages = list(result.scalars().all())
        for i, m in enumerate(messages):
            if m.id == assistant_message_id and i > 0:
                prev = messages[i - 1]
                if prev.role == "user":
                    return prev.content
        return None

    async def _resolve_chunk_ids(
        self,
        msg: Message,
        explicit_chunk_id: str | None,
        explicit_chunk_ids: list[str] | None = None,
    ) -> list[str]:
        if explicit_chunk_ids:
            seen: set[str] = set()
            out: list[str] = []
            for cid in explicit_chunk_ids:
                if cid and cid not in seen:
                    seen.add(cid)
                    out.append(cid)
            if out:
                return out
        if explicit_chunk_id:
            return [explicit_chunk_id]
        sources = msg.sources
        if sources is None:
            return []
        if isinstance(sources, str):
            try:
                sources = json.loads(sources)
            except json.JSONDecodeError:
                return []
        if not isinstance(sources, list):
            return []
        ids: list[str] = []
        for s in sources:
            if isinstance(s, dict) and s.get("chunk_id"):
                ids.append(s["chunk_id"])
        return ids
