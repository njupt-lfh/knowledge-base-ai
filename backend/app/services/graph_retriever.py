"""图谱检索服务（Phase 3 Graph-Lite + Phase 3b LinearRAG）。

职责：
    按 GRAPH_MODE 分发检索：lite（BFS+G-L2）、linear（实体倒排+共现）、legacy（旧 BFS）。

在流水线中的位置：
    AgentOrchestrator._retrieve → GraphRetriever.search
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.chunk import Chunk
from .entity_index_service import normalize_graph_mode, search_entity_index
from .graph_store_service import (
    build_networkx_graph,
    expand_graph_paths,
    link_entities_in_query,
    list_entity_names,
)
from .multi_hop_retrieval_service import get_multi_hop_anchors

logger = logging.getLogger(__name__)


class GraphRetriever:
    """知识图谱检索器（GRAPH_MODE 可切换）。"""

    async def search(
        self,
        db: AsyncSession,
        kb_id: str,
        query: str,
        *,
        top_k: int | None = None,
        graph_mode: str | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """执行图谱检索。

        参数:
            db: 数据库会话
            kb_id: 知识库 ID
            query: 用户查询
            top_k: 返回 chunk 条数
            graph_mode: 覆盖 settings.GRAPH_MODE（lite|linear|legacy）

        返回:
            (sources, graph_paths)
        """
        from ..core import chat_runtime as rt

        if not rt.get_bool("GRAPH_ENABLED", True):
            return [], []

        mode = normalize_graph_mode(graph_mode)
        if mode == "linear":
            return await search_entity_index(db, kb_id, query, top_k=top_k)

        if mode == "legacy":
            return await self._search_legacy_bfs(db, kb_id, query, top_k=top_k)
        return await self._search_graph_lite(db, kb_id, query, top_k=top_k)

    async def _search_graph_lite(
        self,
        db: AsyncSession,
        kb_id: str,
        query: str,
        *,
        top_k: int | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Graph-Lite：G-L1 分解 + G-L2 硬过滤 BFS。"""
        k = top_k or getattr(settings, "RETRIEVAL_TOP_K", 5)
        max_hops = getattr(settings, "GRAPH_MAX_HOPS", 2)

        entity_names = await list_entity_names(db, kb_id)
        if not entity_names:
            return [], []

        seeds = link_entities_in_query(query, entity_names)
        if not seeds:
            decomposed = get_multi_hop_anchors(query)
            if decomposed:
                seeds = link_entities_in_query(" ".join(decomposed), entity_names)
        if not seeds:
            return [], []

        return await self._finalize_chunk_sources(
            db,
            kb_id,
            query,
            seeds=seeds,
            top_k=k,
            max_hops=max_hops,
            anchor_hard_filter=True,
            source_label="graph",
            graph_mode="lite",
        )

    async def _search_legacy_bfs(
        self,
        db: AsyncSession,
        kb_id: str,
        query: str,
        *,
        top_k: int | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """legacy：仅子串 linking，无 G-L1 分解，无 G-L2 硬过滤。"""
        k = top_k or getattr(settings, "RETRIEVAL_TOP_K", 5)
        max_hops = getattr(settings, "GRAPH_MAX_HOPS", 2)

        entity_names = await list_entity_names(db, kb_id)
        if not entity_names:
            return [], []

        seeds = link_entities_in_query(query, entity_names)
        if not seeds:
            return [], []

        return await self._finalize_chunk_sources(
            db,
            kb_id,
            query,
            seeds=seeds,
            top_k=k,
            max_hops=max_hops,
            anchor_hard_filter=False,
            source_label="graph",
            graph_mode="legacy",
        )

    async def _finalize_chunk_sources(
        self,
        db: AsyncSession,
        kb_id: str,
        query: str,
        *,
        seeds: list[str],
        top_k: int,
        max_hops: int,
        anchor_hard_filter: bool,
        source_label: str,
        graph_mode: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """BFS 扩展后加载 chunk 并组装 sources。"""
        effective_k = top_k
        if len(seeds) >= 2:
            effective_k = min(top_k * 2, 12)

        graph = await build_networkx_graph(db, kb_id)
        chunk_scores, paths = expand_graph_paths(
            graph,
            seeds,
            max_hops=max_hops,
            anchor_hard_filter=anchor_hard_filter,
        )
        if not chunk_scores:
            return [], paths

        ranked_ids = sorted(chunk_scores.keys(), key=lambda x: chunk_scores[x], reverse=True)[
            : max(effective_k * 2, 10)
        ]
        chunks = (
            (
                await db.execute(
                    select(Chunk).where(
                        Chunk.id.in_(ranked_ids),
                        Chunk.knowledge_base_id == kb_id,
                        Chunk.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        chunk_map = {c.id: c for c in chunks}

        sources: list[dict[str, Any]] = []
        for cid in ranked_ids:
            chunk = chunk_map.get(cid)
            if not chunk:
                continue
            sources.append(
                {
                    "chunk_id": cid,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "document_id": chunk.document_id,
                    "score": round(chunk_scores[cid], 6),
                    "source": source_label,
                    "graph_seeds": seeds,
                    "graph_mode": graph_mode,
                }
            )
        return sources[:effective_k], paths
