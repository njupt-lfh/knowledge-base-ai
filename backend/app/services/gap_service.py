"""知识缺口（Gap）队列服务 — classify_gap + 对话后入队 + 批准入库。

职责：
    对话/RAG 后自动分类知识缺失类型，结合 CRAG 结果去重入队，
    支持用户纠正/补充事实的结构化提炼与批准入库。

在流水线中的位置：
    ChatService.chat_stream → GapService.process_after_chat
    API gaps 路由 → list / ingest_gap

依赖服务：
    - ConversationExtractService：可入库类型结构化抽取
    - DocumentService.ingest_manual_immediate：Gap 批准入库
    - EmbeddingService：弱命中探测
"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.chroma_client import get_collection
from ..models.knowledge_gap import GAP_STATUSES, GAP_TYPES, KnowledgeGap
from ..utils.kb_id import KbIdResolver
from .conversation_extract_service import AUTO_INGEST_GAP_TYPES, ConversationExtractService
from .document_service import DocumentService
from .embedding_service import EmbeddingService

# 弱命中：向量距离换算 score 高于此值，但未进入最终 context
WEAK_HIT_SCORE = 0.25
# 库内无相关证据
ABSENT_SCORE = 0.2
# 与 rag_service.SYSTEM_PROMPT 拒答话术保持一致（中英文）
NO_INFO_PHRASES = (
    "暂无相关信息",
    "暂无相关内容",
    "知识库中暂无",
    "目前知识库中暂无",
    "没有相关信息",
    "未找到相关",
    "无法找到相关",
    "no relevant information",
    "no information available",
    "not found in the knowledge",
)


class GapService:
    """知识缺口分类、入队与批准入库。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.embed_svc = EmbeddingService()
        self._kb_resolver = KbIdResolver(db)

    async def _canonical_kb_id(self, kb_id: str) -> str:
        """解析为规范知识库 ID（兼容 legacy 前缀）。

        参数:
            kb_id: 原始 ID

        返回:
            规范 ID
        """
        return await self._kb_resolver.resolve(kb_id)

    def _gap_kb_clause(self, canonical: str):
        """构建 Gap 查询的 kb_id IN 子句（含 legacy）。

        参数:
            canonical: 规范 ID

        返回:
            SQLAlchemy 布尔表达式
        """
        legacy = KbIdResolver.legacy_prefix(canonical)
        ids = [canonical] if legacy == canonical else [canonical, legacy]
        return KnowledgeGap.kb_id.in_(ids)

    def classify_gap(
        self,
        query: str,
        kb_id: str,
        retrieval_result: list[dict],
        *,
        correction_text: str | None = None,
        user_message: str | None = None,
    ) -> str:
        """根据检索结果与用户输入分类 Gap 类型。

        参数:
            query: 用户问题
            kb_id: 知识库 ID
            retrieval_result: RAG 检索来源
            correction_text: 纠正文本
            user_message: 用户原话

        返回:
            GAP_TYPES 之一（如 KNOWLEDGE_ABSENT、RETRIEVAL_MISS）
        """
        if correction_text and correction_text.strip():
            return "USER_CORRECTION"

        if user_message and self._looks_like_user_fact(user_message):
            return "USER_PROVIDED"

        if not retrieval_result:
            weak = self._probe_weak_hits(kb_id, query)
            return "RETRIEVAL_MISS" if weak else "KNOWLEDGE_ABSENT"

        max_score = max((s.get("score") or 0) for s in retrieval_result)
        if max_score < ABSENT_SCORE:
            weak = self._probe_weak_hits(kb_id, query)
            return "RETRIEVAL_MISS" if weak else "KNOWLEDGE_ABSENT"

        return "RETRIEVAL_MISS"

    def _probe_weak_hits(self, kb_id: str, query: str) -> bool:
        """向量探测是否存在弱相关 chunk（区分 RETRIEVAL_MISS vs ABSENT）。

        参数:
            kb_id: 知识库 ID
            query: 查询

        返回:
            是否存在弱命中
        """
        try:
            collection = get_collection(kb_id)
            emb = self.embed_svc.embed_query(query)
            results = collection.query(query_embeddings=[emb], n_results=5)
            if not results or not results.get("distances") or not results["distances"][0]:
                return False
            for dist in results["distances"][0]:
                if 0.7 * (1 - dist) >= WEAK_HIT_SCORE:
                    return True
        except Exception:
            return False
        return False

    @staticmethod
    def _looks_like_user_fact(text: str) -> bool:
        """启发式判断用户是否在陈述可入库事实。

        参数:
            text: 用户消息

        返回:
            是否像事实陈述
        """
        t = text.strip()
        if len(t) < 12:
            return False
        markers = ("是", "为", "等于", "指的是", "定义为", "应该", "需要")
        return any(m in t for m in markers) and "?" not in t and "？" not in t

    @staticmethod
    def should_skip_gap_after_sufficient_answer(
        *,
        crag_sufficient: bool,
        crag_refused: bool,
        gap_type: str,
    ) -> bool:
        """CRAG 已判定检索充分且未拒答时，不再记「知识缺失/检索未命中」类假缺口。"""
        if not crag_sufficient or crag_refused:
            return False
        return gap_type in ("KNOWLEDGE_ABSENT", "RETRIEVAL_MISS")

    @staticmethod
    def should_enqueue(
        retrieval_result: list[dict],
        answer: str,
    ) -> bool:
        """判断是否应入 Gap 队列（低分或拒答话术）。

        参数:
            retrieval_result: 检索来源
            answer: 助手回答

        返回:
            是否入队
        """
        if not retrieval_result:
            return True
        max_score = max((s.get("score") or 0) for s in retrieval_result)
        if max_score < ABSENT_SCORE:
            return True
        if any(p in (answer or "") for p in NO_INFO_PHRASES):
            return True
        return False

    async def create_gap(
        self,
        *,
        kb_id: str,
        query: str,
        gap_type: str,
        conversation_id: str | None = None,
        message_id: str | None = None,
        source_ref: str | None = None,
        suggested_content: str | None = None,
        retrieval_result: list[dict] | None = None,
        confidence: float | None = None,
    ) -> KnowledgeGap:
        """创建 Gap 记录。

        参数:
            kb_id: 知识库 ID
            query: 关联问题
            gap_type: 缺口类型
            conversation_id: 对话 ID
            message_id: 消息 ID
            source_ref: 来源引用
            suggested_content: 建议入库 JSON
            retrieval_result: 检索快照
            confidence: 置信度

        返回:
            KnowledgeGap 实体

        Raises:
            ValueError: 非法 gap_type
        """
        if gap_type not in GAP_TYPES:
            raise ValueError(f"invalid gap_type: {gap_type}")

        kb_id = await self._canonical_kb_id(kb_id)
        status = "manual_required" if gap_type == "KNOWLEDGE_ABSENT" else "pending"
        if gap_type in ("USER_PROVIDED", "USER_CORRECTION"):
            status = "suggested"

        ref = source_ref
        if ref is None and retrieval_result:
            ref = json.dumps(
                [
                    {"chunk_id": s.get("chunk_id"), "score": s.get("score")}
                    for s in retrieval_result[:5]
                ],
                ensure_ascii=False,
            )

        gap = KnowledgeGap(
            kb_id=kb_id,
            query=query,
            conversation_id=conversation_id,
            message_id=message_id,
            gap_type=gap_type,
            status=status,
            suggested_content=suggested_content,
            source_ref=ref,
            confidence=confidence,
        )
        self.db.add(gap)
        await self.db.commit()
        await self.db.refresh(gap)
        return gap

    async def _find_open_gap(self, kb_id: str, query: str) -> KnowledgeGap | None:
        """查找同 query 的未关闭 Gap（去重用）。

        参数:
            kb_id: 知识库 ID
            query: 问题文本

        返回:
            已存在的 Gap 或 None
        """
        canonical = await self._canonical_kb_id(kb_id)
        existing = await self.db.execute(
            select(KnowledgeGap).where(
                self._gap_kb_clause(canonical),
                KnowledgeGap.query == query,
                KnowledgeGap.status.in_(("pending", "suggested", "manual_required")),
            )
        )
        return existing.scalar_one_or_none()

    async def process_after_chat(
        self,
        *,
        kb_id: str,
        query: str,
        answer: str,
        sources: list[dict],
        conversation_id: str,
        message_id: str,
        crag_sufficient: bool = False,
        crag_refused: bool = False,
    ) -> KnowledgeGap | None:
        """对话结束后：分类 → 结构化提炼（可入库类型）→ 入队。

        参数:
            kb_id: 知识库 ID
            query: 用户问题
            answer: 助手回答
            sources: RAG 来源
            conversation_id: 对话 ID
            message_id: 消息 ID
            crag_sufficient: CRAG 是否判定充分
            crag_refused: 是否 CRAG 拒答

        返回:
            新建的 Gap 或 None（跳过/去重）
        """
        if await self._find_open_gap(kb_id, query):
            return None

        gap_type = self.classify_gap(query, kb_id, sources, user_message=query)

        if self.should_skip_gap_after_sufficient_answer(
            crag_sufficient=crag_sufficient,
            crag_refused=crag_refused,
            gap_type=gap_type,
        ):
            return None

        if gap_type == "KNOWLEDGE_ABSENT":
            if not self.should_enqueue(sources, answer):
                return None
            return await self.create_gap(
                kb_id=kb_id,
                query=query,
                gap_type=gap_type,
                conversation_id=conversation_id,
                message_id=message_id,
                retrieval_result=sources,
            )

        if gap_type in AUTO_INGEST_GAP_TYPES:
            extracted = await ConversationExtractService().extract_from_turn(
                query, answer, hint_gap_type=gap_type
            )
            if extracted:
                return await self.create_gap(
                    kb_id=kb_id,
                    query=query,
                    gap_type=extracted["gap_type"],
                    conversation_id=conversation_id,
                    message_id=message_id,
                    source_ref=extracted["source_ref"],
                    suggested_content=ConversationExtractService.pack_suggested(extracted),
                    retrieval_result=sources,
                    confidence=0.85,
                )

        if not self.should_enqueue(sources, answer):
            return None

        return await self.create_gap(
            kb_id=kb_id,
            query=query,
            gap_type=gap_type,
            conversation_id=conversation_id,
            message_id=message_id,
            retrieval_result=sources,
        )

    async def maybe_enqueue_from_chat(
        self,
        *,
        kb_id: str,
        query: str,
        answer: str,
        sources: list[dict],
        conversation_id: str,
        message_id: str,
    ) -> KnowledgeGap | None:
        """maybe_enqueue_from_chat 别名，兼容旧调用。

        参数/返回: 同 process_after_chat
        """
        return await self.process_after_chat(
            kb_id=kb_id,
            query=query,
            answer=answer,
            sources=sources,
            conversation_id=conversation_id,
            message_id=message_id,
        )

    async def ingest_gap(
        self,
        kb_id: str,
        gap_id: str,
        *,
        manual_content: str | None = None,
        manual_title: str | None = None,
    ) -> dict:
        """批准 Gap 并同步入库。

        参数:
            kb_id: 知识库 ID
            gap_id: Gap ID
            manual_content: 人工填写内容（ABSENT 必填）
            manual_title: 可选标题

        返回:
            含 document_id、ingest 统计的 dict

        Raises:
            ValueError: Gap 不存在或内容不合法
        """
        canonical = await self._canonical_kb_id(kb_id)
        gap = await self.db.get(KnowledgeGap, gap_id)
        if not gap or not self._kb_resolver.gap_kb_matches(gap.kb_id, canonical):
            raise ValueError("gap not found")
        if gap.kb_id != canonical:
            gap.kb_id = canonical

        if gap.gap_type == "KNOWLEDGE_ABSENT":
            content = (manual_content or "").strip()
            if not content:
                raise ValueError("KNOWLEDGE_ABSENT 需人工填写内容，禁止 LLM 自动生成")
            title = manual_title or gap.query[:30]
            source_ref = content[:300]
        elif gap.gap_type in AUTO_INGEST_GAP_TYPES:
            if not gap.source_ref:
                raise ValueError("缺少 source_ref，拒绝入库")
            suggested: dict = {}
            if gap.suggested_content:
                try:
                    suggested = json.loads(gap.suggested_content)
                except json.JSONDecodeError:
                    suggested = {}
            content = (manual_content or suggested.get("content") or "").strip()
            if not content and gap.gap_type in ("USER_CORRECTION", "USER_PROVIDED"):
                content = (gap.source_ref or "").strip()
            if not content:
                raise ValueError("无入库内容")
            title = manual_title or suggested.get("title") or gap.query[:30]
            source_ref = gap.source_ref
        else:
            raise ValueError(f"gap_type {gap.gap_type} 不支持自动入库")

        doc_svc = DocumentService(self.db)
        doc, stats = await doc_svc.ingest_manual_immediate(canonical, f"[Gap] {title}", content)
        gap.status = "approved"
        gap.source_ref = source_ref
        await self.db.commit()
        await self.db.refresh(gap)
        return {
            "gap_id": gap.id,
            "document_id": doc.id,
            "ingest_allowed": stats.allowed,
            "ingest_duplicates": stats.duplicates,
            "ingest_conflicts": stats.conflicts,
        }

    async def list_gaps(
        self,
        kb_id: str,
        *,
        gap_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[KnowledgeGap]:
        """列出 Gap 队列。

        参数:
            kb_id: 知识库 ID
            gap_type: 类型过滤
            status: 状态过滤
            limit: 最大条数

        返回:
            KnowledgeGap 列表
        """
        canonical = await self._canonical_kb_id(kb_id)
        q = select(KnowledgeGap).where(self._gap_kb_clause(canonical))
        if gap_type:
            q = q.where(KnowledgeGap.gap_type == gap_type)
        if status:
            q = q.where(KnowledgeGap.status == status)
        q = q.order_by(KnowledgeGap.created_at.desc()).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def update_status(self, gap_id: str, status: str) -> KnowledgeGap | None:
        """更新 Gap 状态。

        参数:
            gap_id: Gap ID
            status: 新状态

        返回:
            更新后的实体或 None

        Raises:
            ValueError: 非法 status
        """
        if status not in GAP_STATUSES:
            raise ValueError(f"invalid status: {status}")
        gap = await self.db.get(KnowledgeGap, gap_id)
        if not gap:
            return None
        gap.status = status
        await self.db.commit()
        await self.db.refresh(gap)
        return gap
