"""图谱检索 — Phase 3: 实体 linking + 多跳扩展 → chunk 排序"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.chunk import Chunk
from .graph_store_service import (
    build_networkx_graph,
    expand_graph_paths,
    link_entities_in_query,
    list_entity_names,
)

logger = logging.getLogger(__name__)


class GraphRetriever:
    async def search(
        self,
        db: AsyncSession,
        kb_id: str,
        query: str,
        *,
        top_k: int | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """返回 (sources, graph_paths)。"""
        if not getattr(settings, "GRAPH_ENABLED", True):
            return [], []

        k = top_k or getattr(settings, "RETRIEVAL_TOP_K", 5)
        max_hops = getattr(settings, "GRAPH_MAX_HOPS", 2)

        entity_names = await list_entity_names(db, kb_id)
        if not entity_names:
            return [], []

        seeds = link_entities_in_query(query, entity_names)
        if not seeds:
            return [], []

        effective_k = k
        if len(seeds) >= 2:
            effective_k = min(k * 2, 12)

        graph = await build_networkx_graph(db, kb_id)
        chunk_scores, paths = expand_graph_paths(graph, seeds, max_hops=max_hops)
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
            score = round(chunk_scores[cid], 6)
            sources.append(
                {
                    "chunk_id": cid,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "document_id": chunk.document_id,
                    "score": score,
                    "source": "graph",
                    "graph_seeds": seeds,
                }
            )
        return sources[:effective_k], paths
