"""知识库 ID 解析 — 兼容误存为 UUID 首段（8 位）的历史数据。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.knowledge_base import KnowledgeBase


class KbIdResolver:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._cache: dict[str, str] = {}

    @staticmethod
    def legacy_prefix(canonical: str) -> str:
        if "-" in canonical:
            return canonical.split("-", 1)[0]
        return canonical[:8]

    async def resolve(self, kb_id: str) -> str:
        raw = (kb_id or "").strip()
        if not raw:
            raise ValueError("knowledge base id required")
        if raw in self._cache:
            return self._cache[raw]

        kb = await self.db.get(KnowledgeBase, raw)
        if kb:
            self._cache[raw] = kb.id
            return kb.id

        result = await self.db.execute(
            select(KnowledgeBase.id).where(KnowledgeBase.id.like(f"{raw}%"))
        )
        ids = list(result.scalars().all())
        if len(ids) == 1:
            self._cache[raw] = ids[0]
            return ids[0]
        if len(ids) > 1:
            raise ValueError("ambiguous knowledge base id prefix")
        raise ValueError("knowledge base not found")

    def gap_kb_matches(self, gap_kb: str, canonical: str) -> bool:
        gap_kb = (gap_kb or "").strip()
        if gap_kb == canonical:
            return True
        return gap_kb == self.legacy_prefix(canonical)
