"""Agentic-lite 编排服务（Phase 2.2: Router + Retrieve + CRAG + 有界 2 轮循环）。

职责：
    统一 Agent 决策流：问题路由 → Hybrid/Graph/SIM-RAG 检索 → CRAG 充分性
    → 最多 2 轮重试 → 拒答或 LLM 流式生成。

在流水线中的位置：
    RAGService.generate → AgentOrchestrator.generate_stream

依赖服务：
    - query_router：问题分类与 top_k / 重试 query 扩展
    - HybridRetriever / GraphRetriever：混合与图谱检索
    - crag_evaluator：充分性评估
    - retrieval_gate：检索 abstention
    - sim_rag_service：多子查询 SIM-RAG
    - history_memory_service：对话历史压缩
    - LLMService：最终回答生成
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..core import chat_runtime as rt
from ..core.config import settings
from .answer_guard_service import REFUSAL_TEXT
from .crag_evaluator import SufficiencyResult, evaluate_sufficiency
from .cross_encoder_rerank_service import cross_encoder_rerank
from .graph_retriever import GraphRetriever
from .history_memory_service import compress_history
from .hybrid_retriever import HybridRetriever, merge_source_lists
from .llm_service import LLMService
from .post_retrieval_filter import apply_post_retrieval_filter
from .query_router import QueryRoute, expand_query_for_retry, retrieval_top_k_for_route, route_query
from .retrieval_gate import apply_retrieval_abstention

logger = logging.getLogger(__name__)

CONSISTENCY_CONFLICT_REFUSAL = (
    "基于不同检索路径生成的答案存在矛盾，为避免提供错误信息，已为您记录此问题，我们将尽快核实补充。"
)
CONSISTENCY_UNCERTAIN_REFUSAL = (
    "基于不同检索路径无法确认答案一致性，已为您记录此问题，我们将尽快核实补充。"
)

CHITCHAT_SYSTEM = """你是知识库平台的智能助手。用户正在进行日常寒暄或通用对话。
请简短、友好地回答，不要编造知识库中不存在的专业事实。"""


@dataclass
class AgentRunResult:
    """单次 Agent 运行结果（供 generate_stream 与评测使用）。"""

    sources: list[dict[str, Any]] = field(default_factory=list)
    route: QueryRoute = "factual"
    sufficient: bool = False
    rounds: int = 0
    skipped_retrieval: bool = False
    sufficiency: SufficiencyResult | None = None
    refused: bool = False
    graph_paths: list[dict[str, Any]] = field(default_factory=list)
    graph_used: bool = False
    sim_rag_used: bool = False
    sim_sub_queries: list[str] = field(default_factory=list)
    sim_coverage: float = 0.0


class AgentOrchestrator:
    """Agentic-lite 编排器：有界 2 轮检索 + CRAG + 流式生成。"""

    def __init__(self):
        self.hybrid = HybridRetriever()
        self.graph = GraphRetriever()
        self.llm = LLMService()

    def _should_use_graph(self, route: QueryRoute, query: str) -> bool:
        """判断是否启用图谱检索（关系型或含多跳关键词）。

        参数:
            route: 问题路由
            query: 用户查询

        返回:
            是否调用 GraphRetriever
        """
        if not rt.get_bool("GRAPH_ENABLED", True):
            return False
        if route == "relational":
            return True
        if route == "comprehensive" and any(k in query for k in ("关联", "两段", "多跳", "之间")):
            return True
        return any(k in query for k in ("关联", "两段", "多跳", "之间"))

    async def _retrieve(
        self,
        db: AsyncSession,
        kb_id: str,
        query: str,
        *,
        route: QueryRoute,
        top_k: int,
        graph_mode: str | None = None,
        skip_abstention: bool = False,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """单轮检索：Hybrid ± Graph，经 abstention 门控。

        参数:
            db: 数据库会话
            kb_id: 知识库 ID
            query: 检索 query
            route: 问题类型
            top_k: 条数上限

        返回:
            (sources, graph_paths) 元组
        """
        hybrid_sources = await self.hybrid.search(db, kb_id, query, top_k=top_k)
        graph_paths: list[dict[str, Any]] = []

        if self._should_use_graph(route, query):
            # 图谱检索：实体 linking + BFS 多跳
            graph_sources, graph_paths = await self.graph.search(
                db,
                kb_id,
                query,
                top_k=top_k,
                graph_mode=graph_mode,
            )
            merged = (
                merge_source_lists([graph_sources, hybrid_sources], top_k=max(top_k * 3, 12))
                if graph_sources
                else hybrid_sources
            )
            # Graph+Hybrid 融合后再统一 CE 重排（graph chunk 单独打分）
            if graph_sources and rt.get_bool("CROSS_ENCODER_RERANK_ENABLED", False):
                pool = min(len(merged), getattr(settings, "HYBRID_RRF_POOL_SIZE", 30))
                merged = cross_encoder_rerank(query, merged, top_k=pool)
                # P1-1: graph 路径关闭 soft_fallback，避免低分噪声进入 context
                merged = apply_post_retrieval_filter(merged, allow_soft_fallback=False)
                merged = merged[:top_k]
            elif graph_sources:
                merged = merged[:top_k]
            if not skip_abstention:
                merged = apply_retrieval_abstention(query, merged, route, graph_paths=graph_paths)
            return merged, graph_paths

        if not skip_abstention:
            hybrid_sources = apply_retrieval_abstention(
                query, hybrid_sources, route, graph_paths=graph_paths
            )
        return hybrid_sources, graph_paths

    async def _retrieve_multi_hop_anchor(
        self,
        db: AsyncSession,
        kb_id: str,
        query: str,
        *,
        route: QueryRoute,
        top_k: int,
        graph_mode: str | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """多跳分路子查询：跳过 abstention，避免 kg 短实体被误清空。"""
        return await self._retrieve(
            db,
            kb_id,
            query,
            route=route,
            top_k=top_k,
            graph_mode=graph_mode,
            skip_abstention=True,
        )

    async def _retrieve_strict(
        self,
        db: AsyncSession,
        kb_id: str,
        query: str,
        *,
        route: QueryRoute,
        top_k: int,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """严格检索路径：关闭 soft fallback + CE τ=0.35（Phase 2 P0-1）。"""
        sources = await self.hybrid.search(
            db,
            kb_id,
            query,
            top_k=top_k,
            allow_soft_fallback=False,
        )
        sources = apply_retrieval_abstention(
            query,
            sources,
            route,
            ce_min_score=0.35,
        )
        return sources, []

    async def _retrieve_relaxed(
        self,
        db: AsyncSession,
        kb_id: str,
        query: str,
        *,
        route: QueryRoute,
        top_k: int,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """扩展检索路径：soft fallback + graph + CE τ=0.25（Phase 2 P0-1）。"""
        sources = await self.hybrid.search(
            db,
            kb_id,
            query,
            top_k=top_k,
            allow_soft_fallback=True,
        )
        paths: list[dict[str, Any]] = []
        if self._should_use_graph(route, query):
            graph_sources, gpaths = await self.graph.search(
                db,
                kb_id,
                query,
                top_k=top_k,
            )
            if graph_sources:
                paths = gpaths
                merged = merge_source_lists(
                    [graph_sources, sources],
                    top_k=max(top_k * 3, 12),
                )
                if rt.get_bool("CROSS_ENCODER_RERANK_ENABLED", False):
                    pool = min(len(merged), getattr(settings, "HYBRID_RRF_POOL_SIZE", 30))
                    merged = cross_encoder_rerank(query, merged, top_k=pool)
                    merged = apply_post_retrieval_filter(
                        merged,
                        allow_soft_fallback=True,
                    )
                    merged = merged[:top_k]
                sources = merged
        sources = apply_retrieval_abstention(
            query,
            sources,
            route,
            graph_paths=paths,
            ce_min_score=0.25,
        )
        return sources, paths

    async def _record_consistency_refusal(
        self,
        db: AsyncSession,
        kb_id: str,
        query: str,
        consistency: Any,
        *,
        route: str,
        sources: list[dict[str, Any]],
    ) -> None:
        """CONFLICT/UNCERTAIN 时写入 answer_review_queue 并关联 Gap。"""
        try:
            from .answer_review_service import AnswerReviewService

            svc = AnswerReviewService(db)
            await svc.record_consistency_issue(
                kb_id=kb_id,
                query=query,
                answer_a=consistency.answer_a,
                answer_b=consistency.answer_b,
                verdict=consistency.verdict,
                ctx_hash=consistency.ctx_hash,
                reason=consistency.reason,
                route=route,
                retrieval_sources=sources,
            )
        except Exception as exc:
            logger.warning("answer review enqueue failed (non-blocking): %s", exc)

    def _consistency_needs_refusal(self, consistency: Any | None) -> bool:
        """判定一致性结果是否应拒答。"""
        if not consistency:
            return False
        if consistency.verdict == "CONFLICT":
            return True
        if consistency.verdict == "UNCERTAIN":
            return getattr(settings, "CONSISTENCY_UNCERTAIN_REFUSE", True)
        return False

    async def _retrieve_enhanced(
        self,
        db: AsyncSession,
        kb_id: str,
        query: str,
        *,
        route: QueryRoute,
        top_k: int,
        graph_mode: str | None = None,
        use_sim_rag: bool = True,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """生产/评测共用：多跳分路 → SIM-RAG → 常规定径。"""
        from .multi_hop_retrieval_service import (
            should_use_multi_hop_split,
            try_multi_hop_split_retrieve,
        )
        from .sim_rag_service import should_use_sim_rag, sim_rag_retrieve

        if should_use_multi_hop_split(route, query):
            split = await try_multi_hop_split_retrieve(
                db,
                kb_id,
                query,
                route=route,
                top_k=top_k,
                retrieve_fn=self._retrieve_multi_hop_anchor,
                graph_mode=graph_mode,
            )
            if split:
                return split

        if use_sim_rag and rt.get_bool("EVAL_SIM_RAG_ENABLED", True):
            if should_use_sim_rag(route, query):
                sim = await sim_rag_retrieve(
                    db,
                    kb_id,
                    query,
                    route=route,
                    hybrid=self.hybrid,
                    retrieve_fn=self._retrieve,
                    top_k=top_k,
                )
                if sim:
                    return sim.sources, sim.graph_paths

        return await self._retrieve(
            db,
            kb_id,
            query,
            route=route,
            top_k=top_k,
            graph_mode=graph_mode,
        )

    async def retrieve_for_eval(
        self,
        db: AsyncSession,
        kb_id: str,
        query: str,
        *,
        top_k: int | None = None,
        graph_mode: str | None = None,
    ) -> tuple[list[dict[str, Any]], QueryRoute, list[dict[str, Any]]]:
        """评测专用：多跳分路 + SIM-RAG + abstention，不走 CRAG 拒答。"""
        route = route_query(query)
        if route == "chitchat":
            return [], route, []
        k = retrieval_top_k_for_route(
            route,
            top_k or getattr(settings, "RETRIEVAL_TOP_K", 5),
            query=query,
        )
        sources, paths = await self._retrieve_enhanced(
            db,
            kb_id,
            query,
            route=route,
            top_k=k,
            graph_mode=graph_mode,
            use_sim_rag=True,
        )
        return sources, route, paths

    async def run(
        self,
        db: AsyncSession,
        kb_id: str,
        query: str,
        *,
        top_k: int | None = None,
    ) -> AgentRunResult:
        """完整 Agent 决策流（最多 2 轮检索 + CRAG）。

        参数:
            db: 数据库会话
            kb_id: 知识库 ID
            query: 用户问题
            top_k: 检索条数

        返回:
            AgentRunResult，含来源、充分性、拒答标记等
        """
        route = route_query(query)
        base_k = top_k or getattr(settings, "RETRIEVAL_TOP_K", 5)

        if route == "chitchat":
            return AgentRunResult(
                sources=[],
                route=route,
                sufficient=True,
                rounds=0,
                skipped_retrieval=True,
                sufficiency=evaluate_sufficiency(query, [], route),
            )

        k = retrieval_top_k_for_route(route, base_k, query=query)
        sim_used = False
        sim_sub: list[str] = []
        sim_cov = 0.0

        sources, graph_paths = await self._retrieve_enhanced(
            db,
            kb_id,
            query,
            route=route,
            top_k=k,
            use_sim_rag=True,
        )
        graph_used = bool(graph_paths) or any(
            s.get("source", "").startswith("graph") for s in sources
        )
        from .multi_hop_retrieval_service import get_multi_hop_anchors

        if (
            rt.get_bool("MULTI_HOP_SPLIT_ENABLED", True)
            and len(get_multi_hop_anchors(query)) >= 2
        ):
            sim_sub = get_multi_hop_anchors(query)
        else:
            from .sim_rag_service import decompose_sub_queries

            sim_sub = decompose_sub_queries(query)
        eval1 = evaluate_sufficiency(query, sources, route)
        max_rounds = max(1, rt.get_int("AGENT_MAX_ROUNDS", 2))

        # 第 1 轮检索充分 → 直接采纳，不重试
        if eval1.sufficient:
            return AgentRunResult(
                sources=sources,
                route=route,
                sufficient=True,
                rounds=1,
                sufficiency=eval1,
                graph_paths=graph_paths,
                graph_used=graph_used,
                sim_rag_used=sim_used,
                sim_sub_queries=sim_sub,
                sim_coverage=sim_cov,
            )

        # AGENT_MAX_ROUNDS=1：跳过第二轮检索，直接采用首轮结果（提速，略降 CRAG 严格度）
        if max_rounds < 2:
            return AgentRunResult(
                sources=sources,
                route=route,
                sufficient=True,
                rounds=1,
                sufficiency=eval1,
                graph_paths=graph_paths,
                graph_used=graph_used,
                sim_rag_used=sim_used,
                sim_sub_queries=sim_sub,
                sim_coverage=sim_cov,
            )

        # 第二轮：扩展 query + 增大 top_k
        retry_query = expand_query_for_retry(query, route)
        retry_k = min(k + 3, 12)
        sources2, graph_paths2 = await self._retrieve_enhanced(
            db,
            kb_id,
            retry_query,
            route=route,
            top_k=retry_k,
            use_sim_rag=True,
        )
        graph_used = (
            graph_used
            or bool(graph_paths2)
            or any(s.get("source", "").startswith("graph") for s in sources2)
        )
        graph_paths = graph_paths2 or graph_paths
        eval2 = evaluate_sufficiency(query, sources2, route)

        if eval2.sufficient:
            # 第 2 轮检索充分 → 采用扩展检索结果
            return AgentRunResult(
                sources=sources2,
                route=route,
                sufficient=True,
                rounds=2,
                sufficiency=eval2,
                graph_paths=graph_paths,
                graph_used=graph_used,
                sim_rag_used=sim_used,
                sim_sub_queries=sim_sub,
                sim_coverage=sim_cov,
            )

        # 两轮均不充分 → 拒答，取 score 较高的一轮来源供 Gap 记录
        best_sources = sources2 if eval2.score >= eval1.score else sources
        best_eval = eval2 if eval2.score >= eval1.score else eval1
        return AgentRunResult(
            sources=best_sources,
            route=route,
            sufficient=False,
            rounds=max_rounds,
            sufficiency=best_eval,
            refused=True,
            graph_paths=graph_paths,
            graph_used=graph_used,
            sim_rag_used=sim_used,
            sim_sub_queries=sim_sub,
            sim_coverage=sim_cov,
        )

    async def generate_stream(
        self,
        db: AsyncSession,
        kb_id: str,
        query: str,
        history: list[dict],
        *,
        top_k: int | None = None,
        system_prompt_template: str,
        compress_context,
    ) -> AsyncGenerator[str, None]:
        """SSE 流式生成：先输出 agent_meta / sources，再 LLM token 流。

        参数:
            db: 数据库会话
            kb_id: 知识库 ID
            query: 用户问题
            history: 历史消息
            top_k: 检索条数
            system_prompt_template: 含 {context} 占位符的系统提示
            compress_context: 上下文压缩 callable

        Yields:
            SSE 事件字符串
        """
        run = await self.run(db, kb_id, query, top_k=top_k)

        meta = {
            "type": "agent_meta",
            "route": run.route,
            "rounds": run.rounds,
            "sufficient": run.sufficient,
            "skipped_retrieval": run.skipped_retrieval,
            "refused": run.refused,
            "crag_score": run.sufficiency.score if run.sufficiency else 0,
            "crag_reason": run.sufficiency.reason if run.sufficiency else "",
            "graph_used": run.graph_used,
            "graph_paths": run.graph_paths[:5] if run.graph_paths else [],
            "sim_rag_used": run.sim_rag_used,
            "sim_sub_queries": run.sim_sub_queries,
            "sim_coverage": run.sim_coverage,
            "fast_mode": rt.is_fast_mode(),
        }
        yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"

        if run.skipped_retrieval:
            # 寒暄：不检索，直接 LLM 简短回复
            messages = [{"role": "system", "content": CHITCHAT_SYSTEM}]
            messages.extend(compress_history(history, recent_turns=2))
            messages.append({"role": "user", "content": query})
            yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"
            async for chunk in self.llm.chat_stream(messages):
                yield chunk
            return

        yield f"data: {json.dumps({'type': 'sources', 'sources': run.sources})}\n\n"

        if run.refused:
            # CRAG 拒答：固定话术，不调用 LLM 编造
            for ch in REFUSAL_TEXT:
                yield f"data: {json.dumps({'type': 'text', 'content': ch})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        await self._bump_hit_counts(db, run.sources)

        # 构建基础 messages（Post-hoc 和非 Post-hoc 路径共用）
        base_context = compress_context(
            run.sources,
            max_chars=getattr(settings, "CONTEXT_MAX_CHARS", 4500),
        )
        messages = [
            {"role": "system", "content": system_prompt_template.format(context=base_context)},
        ]
        messages.extend(compress_history(history))
        messages.append({"role": "user", "content": query})

        if rt.get_bool("POST_HOC_ANSWER_GUARD_ENABLED", True):
            from .answer_consistency_service import (
                ConsistencyResult,
                check_consistency,
                should_enable_consistency,
            )
            from .answer_guard_service import verify_answer_grounded

            consistency: ConsistencyResult | None = None
            top_k = retrieval_top_k_for_route(
                run.route,
                getattr(settings, "RETRIEVAL_TOP_K", 5),
                query=query,
            )

            if should_enable_consistency(run.route):
                # Phase 2 P0-1: Path-A strict (τ=0.35, no soft fallback)
                #               Path-B relaxed (τ=0.25, soft fallback + graph)
                try:
                    sources_a, _ = await self._retrieve_strict(
                        db,
                        kb_id,
                        query,
                        route=run.route,
                        top_k=top_k,
                    )
                    sources_b, _ = await self._retrieve_relaxed(
                        db,
                        kb_id,
                        query,
                        route=run.route,
                        top_k=top_k,
                    )
                    if sources_a and sources_b:
                        ctx_a = compress_context(
                            sources_a,
                            max_chars=getattr(settings, "CONTEXT_MAX_CHARS", 4500),
                        )
                        ctx_b = compress_context(
                            sources_b,
                            max_chars=getattr(settings, "CONTEXT_MAX_CHARS", 4500),
                        )
                        msg_a = [
                            {
                                "role": "system",
                                "content": system_prompt_template.format(context=ctx_a),
                            },
                        ]
                        msg_a.extend(compress_history(history))
                        msg_a.append({"role": "user", "content": query})
                        msg_b = [
                            {
                                "role": "system",
                                "content": system_prompt_template.format(context=ctx_b),
                            },
                        ]
                        msg_b.extend(compress_history(history))
                        msg_b.append({"role": "user", "content": query})

                        # 并行生成两个答案
                        ans_a, ans_b = await asyncio.gather(
                            self.llm.chat_completion(msg_a, temperature=0.3, max_tokens=1024),
                            self.llm.chat_completion(msg_b, temperature=0.3, max_tokens=1024),
                            return_exceptions=True,
                        )
                        if isinstance(ans_a, Exception):
                            ans_a = ""
                        if isinstance(ans_b, Exception):
                            ans_b = ""

                        if ans_a and ans_b:
                            consistency = await check_consistency(
                                query=query,
                                answer_a=str(ans_a),
                                answer_b=str(ans_b),
                            )

                        # 用 Path-A 的 context 作为最终 context
                        full_answer = str(ans_a) if ans_a else ""
                        context = ctx_a

                        if consistency and consistency.verdict == "CONFLICT":
                            logger.warning(
                                "consistency CONFLICT route=%s query=%.80s",
                                run.route,
                                query,
                            )
                        elif consistency and consistency.verdict == "UNCERTAIN":
                            logger.warning(
                                "consistency UNCERTAIN route=%s query=%.80s",
                                run.route,
                                query,
                            )
                    else:
                        # 任一路径空检索 → 回退到 run() sources
                        context = compress_context(
                            run.sources,
                            max_chars=getattr(settings, "CONTEXT_MAX_CHARS", 4500),
                        )
                        messages = [
                            {
                                "role": "system",
                                "content": system_prompt_template.format(context=context),
                            },
                        ]
                        messages.extend(compress_history(history))
                        messages.append({"role": "user", "content": query})
                        full_answer = await self.llm.chat_completion(
                            messages,
                            temperature=0.7,
                            max_tokens=2048,
                        )
                except Exception as exc:
                    logger.warning("consistency check failed (non-blocking): %s", exc)
                    # 回退
                    context = compress_context(
                        run.sources,
                        max_chars=getattr(settings, "CONTEXT_MAX_CHARS", 4500),
                    )
                    messages = [
                        {
                            "role": "system",
                            "content": system_prompt_template.format(context=context),
                        },
                    ]
                    messages.extend(compress_history(history))
                    messages.append({"role": "user", "content": query})
                    full_answer = await self.llm.chat_completion(
                        messages,
                        temperature=0.7,
                        max_tokens=2048,
                    )
            else:
                # 非一致性路由：使用 run() 的来源
                context = compress_context(
                    run.sources,
                    max_chars=getattr(settings, "CONTEXT_MAX_CHARS", 4500),
                )
                messages = [
                    {"role": "system", "content": system_prompt_template.format(context=context)},
                ]
                messages.extend(compress_history(history))
                messages.append({"role": "user", "content": query})
                full_answer = await self.llm.chat_completion(
                    messages,
                    temperature=0.7,
                    max_tokens=2048,
                )

            ctx_for_guard = locals().get("context") or compress_context(
                run.sources,
                max_chars=getattr(settings, "CONTEXT_MAX_CHARS", 4500),
            )
            ans_for_guard = locals().get("full_answer", "")
            _passed, final_answer = await verify_answer_grounded(
                query,
                ctx_for_guard,
                ans_for_guard,
                llm=self.llm,
            )

            # 一致性 CONFLICT/UNCERTAIN → 入队 + 拒答话术
            if self._consistency_needs_refusal(consistency):
                await self._record_consistency_refusal(
                    db,
                    kb_id,
                    query,
                    consistency,
                    route=run.route,
                    sources=run.sources,
                )
                if consistency.verdict == "UNCERTAIN":
                    refusal = CONSISTENCY_UNCERTAIN_REFUSAL
                else:
                    refusal = CONSISTENCY_CONFLICT_REFUSAL
                for ch in refusal:
                    yield f"data: {json.dumps({'type': 'text', 'content': ch}, ensure_ascii=False)}\n\n"
            else:
                for ch in final_answer:
                    yield f"data: {json.dumps({'type': 'text', 'content': ch}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        async for chunk in self.llm.chat_stream(messages):
            yield chunk

    @staticmethod
    async def _bump_hit_counts(db: AsyncSession, sources: list[dict[str, Any]]) -> None:
        """递增被引用 chunk 的 hit_count（质量分输入）。

        参数:
            db: 数据库会话
            sources: 最终采用的检索来源
        """
        if not sources:
            return
        try:
            from ..models.chunk import Chunk

            for s in sources:
                chunk = await db.get(Chunk, s["chunk_id"])
                if chunk:
                    chunk.hit_count = (chunk.hit_count or 0) + 1
            await db.commit()
        except Exception:
            logger.debug("hit_count bump skipped", exc_info=True)
