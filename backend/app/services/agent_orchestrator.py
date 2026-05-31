"""Agentic-lite 编排 — Phase 2.2: Router + Retrieve + CRAG + 有界 2 轮循环"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from .crag_evaluator import SufficiencyResult, evaluate_sufficiency
from .graph_retriever import GraphRetriever
from .history_memory_service import compress_history
from .hybrid_retriever import HybridRetriever, merge_source_lists
from .llm_service import LLMService
from .query_router import QueryRoute, expand_query_for_retry, retrieval_top_k_for_route, route_query
from .retrieval_gate import apply_retrieval_abstention

logger = logging.getLogger(__name__)

REFUSAL_TEXT = "目前知识库中暂无相关信息，已为您记录到知识缺口队列，请稍后补充资料或联系管理员。"

CHITCHAT_SYSTEM = """你是知识库平台的智能助手。用户正在进行日常寒暄或通用对话。
请简短、友好地回答，不要编造知识库中不存在的专业事实。"""


@dataclass
class AgentRunResult:
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
    MAX_ROUNDS = 2

    def __init__(self):
        self.hybrid = HybridRetriever()
        self.graph = GraphRetriever()
        self.llm = LLMService()

    def _should_use_graph(self, route: QueryRoute, query: str) -> bool:
        if not getattr(settings, "GRAPH_ENABLED", True):
            return False
        if route == "relational":
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
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        hybrid_sources = await self.hybrid.search(db, kb_id, query, top_k=top_k)
        graph_paths: list[dict[str, Any]] = []

        if self._should_use_graph(route, query):
            graph_sources, graph_paths = await self.graph.search(db, kb_id, query, top_k=top_k)
            merged = (
                merge_source_lists([graph_sources, hybrid_sources], top_k=top_k)
                if graph_sources
                else hybrid_sources
            )
            merged = apply_retrieval_abstention(query, merged, route, graph_paths=graph_paths)
            return merged, graph_paths

        hybrid_sources = apply_retrieval_abstention(
            query, hybrid_sources, route, graph_paths=graph_paths
        )
        return hybrid_sources, graph_paths

    async def retrieve_for_eval(
        self,
        db: AsyncSession,
        kb_id: str,
        query: str,
        *,
        top_k: int | None = None,
    ) -> tuple[list[dict[str, Any]], QueryRoute, list[dict[str, Any]]]:
        """评测专用：单轮检索 + abstention，不走 CRAG 拒答。"""
        route = route_query(query)
        if route == "chitchat":
            return [], route, []
        k = retrieval_top_k_for_route(route, top_k or getattr(settings, "RETRIEVAL_TOP_K", 5))
        sources, paths = await self._retrieve(db, kb_id, query, route=route, top_k=k)
        return sources, route, paths

    async def run(
        self,
        db: AsyncSession,
        kb_id: str,
        query: str,
        *,
        top_k: int | None = None,
    ) -> AgentRunResult:
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

        k = retrieval_top_k_for_route(route, base_k)
        sim_used = False
        sim_sub: list[str] = []
        sim_cov = 0.0

        from .sim_rag_service import should_use_sim_rag, sim_rag_retrieve

        if should_use_sim_rag(route, query):
            sim = await sim_rag_retrieve(
                db,
                kb_id,
                query,
                route=route,
                hybrid=self.hybrid,
                retrieve_fn=self._retrieve,
                top_k=k,
            )
            if sim:
                sim_used = True
                sim_sub = sim.sub_queries
                sim_cov = sim.coverage
                sources = sim.sources
                graph_paths = sim.graph_paths
                graph_used = bool(graph_paths) or any(
                    s.get("source", "").startswith("graph") for s in sources
                )
                eval1 = sim.sufficiency
            else:
                sources, graph_paths = await self._retrieve(db, kb_id, query, route=route, top_k=k)
                graph_used = bool(graph_paths) or any(
                    s.get("source", "").startswith("graph") for s in sources
                )
                eval1 = evaluate_sufficiency(query, sources, route)
        else:
            sources, graph_paths = await self._retrieve(db, kb_id, query, route=route, top_k=k)
            graph_used = bool(graph_paths) or any(
                s.get("source", "").startswith("graph") for s in sources
            )
            eval1 = evaluate_sufficiency(query, sources, route)

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

        retry_query = expand_query_for_retry(query, route)
        retry_k = min(k + 3, 12)
        sources2, graph_paths2 = await self._retrieve(
            db, kb_id, retry_query, route=route, top_k=retry_k
        )
        graph_used = (
            graph_used
            or bool(graph_paths2)
            or any(s.get("source", "").startswith("graph") for s in sources2)
        )
        graph_paths = graph_paths2 or graph_paths
        eval2 = evaluate_sufficiency(query, sources2, route)

        if eval2.sufficient:
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

        best_sources = sources2 if eval2.score >= eval1.score else sources
        best_eval = eval2 if eval2.score >= eval1.score else eval1
        return AgentRunResult(
            sources=best_sources,
            route=route,
            sufficient=False,
            rounds=self.MAX_ROUNDS,
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
        }
        yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"

        if run.skipped_retrieval:
            messages = [{"role": "system", "content": CHITCHAT_SYSTEM}]
            messages.extend(compress_history(history, recent_turns=2))
            messages.append({"role": "user", "content": query})
            yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"
            async for chunk in self.llm.chat_stream(messages):
                yield chunk
            return

        yield f"data: {json.dumps({'type': 'sources', 'sources': run.sources})}\n\n"

        if run.refused:
            for ch in REFUSAL_TEXT:
                yield f"data: {json.dumps({'type': 'text', 'content': ch})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        await self._bump_hit_counts(db, run.sources)

        context = compress_context(
            run.sources,
            max_chars=getattr(settings, "CONTEXT_MAX_CHARS", 4500),
        )
        messages = [{"role": "system", "content": system_prompt_template.format(context=context)}]
        messages.extend(compress_history(history))
        messages.append({"role": "user", "content": query})

        async for chunk in self.llm.chat_stream(messages):
            yield chunk

    @staticmethod
    async def _bump_hit_counts(db: AsyncSession, sources: list[dict[str, Any]]) -> None:
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
