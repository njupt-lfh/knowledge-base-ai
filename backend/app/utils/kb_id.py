"""知识库 ID 解析工具。

导出 `KbIdResolver`，兼容误存为 UUID 首段（8 位）的历史 gap 数据，
在缺口队列、统计等 API 中将路径参数解析为规范 UUID 并做前缀匹配校验。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.knowledge_base import KnowledgeBase


class KbIdResolver:
    """知识库 ID 解析器，带请求级内存缓存。

    支持完整 UUID 精确匹配，以及唯一前缀模糊匹配（历史数据兼容）。
    """

    def __init__(self, db: AsyncSession):
        """初始化解析器。

        参数:
            db: 异步数据库会话，用于查询 knowledge_bases 表。
        """
        self.db = db
        self._cache: dict[str, str] = {}

    @staticmethod
    def legacy_prefix(canonical: str) -> str:
        """提取规范 UUID 的历史短前缀（连字符前段或前 8 字符）。

        参数:
            canonical: 完整知识库 UUID。

        返回:
            用于与旧 gap 记录 kb_id 比对的前缀字符串。
        """
        if "-" in canonical:
            return canonical.split("-", 1)[0]
        return canonical[:8]

    async def resolve(self, kb_id: str) -> str:
        """将路径或请求中的 kb_id 解析为规范 UUID。

        参数:
            kb_id: 完整 UUID 或唯一前缀。

        返回:
            规范的知识库 UUID。

        异常:
            ValueError: ID 为空、前缀歧义或知识库不存在。
        """
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
        """判断缺口记录中的 kb_id 是否与规范 ID 匹配（含历史前缀）。

        参数:
            gap_kb: 缺口表存储的 kb_id。
            canonical: 已解析的规范 UUID。

        返回:
            完全相等或等于 legacy 前缀时为 True。
        """
        gap_kb = (gap_kb or "").strip()
        if gap_kb == canonical:
            return True
        return gap_kb == self.legacy_prefix(canonical)
