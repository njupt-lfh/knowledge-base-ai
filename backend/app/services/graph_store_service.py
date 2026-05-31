"""轻量知识图谱存储 — SQLite 三元组 + NetworkX 内存图"""

from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Any

import networkx as nx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.chunk import Chunk
from ..models.kg_relation import KgRelation
from .entity_extraction_service import extract_triples_from_chunk

logger = logging.getLogger(__name__)

_graph_cache: OrderedDict[str, nx.DiGraph] = OrderedDict()
_CACHE_MAX = 8


def _cache_get(kb_id: str) -> nx.DiGraph | None:
    g = _graph_cache.get(kb_id)
    if g is not None:
        _graph_cache.move_to_end(kb_id)
    return g


def _cache_set(kb_id: str, graph: nx.DiGraph) -> None:
    _graph_cache[kb_id] = graph
    _graph_cache.move_to_end(kb_id)
    while len(_graph_cache) > _CACHE_MAX:
        _graph_cache.popitem(last=False)


def invalidate_graph_cache(kb_id: str) -> None:
    _graph_cache.pop(kb_id, None)


async def delete_relations_for_chunk(
    db: AsyncSession, chunk_id: str, *, commit: bool = True
) -> None:
    await db.execute(delete(KgRelation).where(KgRelation.chunk_id == chunk_id))
    if commit:
        await db.commit()


async def sync_chunk_graph(
    db: AsyncSession,
    kb_id: str,
    chunk_id: str,
    document_id: str,
    content: str,
    *,
    active: bool = True,
    commit: bool = True,
) -> int:
    """抽取并写入 chunk 关联三元组；返回写入条数。"""
    if not getattr(settings, "GRAPH_ENABLED", True):
        return 0

    await delete_relations_for_chunk(db, chunk_id, commit=False)
    if not active or not content.strip():
        invalidate_graph_cache(kb_id)
        if commit:
            await db.commit()
        return 0

    triples = await extract_triples_from_chunk(content)
    if not triples:
        invalidate_graph_cache(kb_id)
        if commit:
            await db.commit()
        return 0

    for t in triples:
        db.add(
            KgRelation(
                knowledge_base_id=kb_id,
                chunk_id=chunk_id,
                document_id=document_id,
                subject=t["subject"],
                predicate=t["predicate"],
                object_entity=t["object"],
                confidence=float(t.get("confidence", 1.0)),
                is_active=True,
            )
        )
    if commit:
        await db.commit()
    invalidate_graph_cache(kb_id)
    return len(triples)


async def sync_chunks_graph(
    db: AsyncSession,
    kb_id: str,
    chunk_records: list[Chunk],
) -> int:
    total = 0
    for c in chunk_records:
        total += await sync_chunk_graph(
            db,
            kb_id,
            c.id,
            c.document_id,
            c.content,
            active=bool(c.is_active if c.is_active is not None else True),
        )
    return total


async def load_relations(db: AsyncSession, kb_id: str) -> list[KgRelation]:
    result = await db.execute(
        select(KgRelation)
        .join(Chunk, Chunk.id == KgRelation.chunk_id)
        .where(
            KgRelation.knowledge_base_id == kb_id,
            KgRelation.is_active.is_(True),
            Chunk.is_active.is_(True),
        )
    )
    return list(result.scalars().all())


async def build_networkx_graph(db: AsyncSession, kb_id: str) -> nx.DiGraph:
    cached = _cache_get(kb_id)
    if cached is not None:
        return cached

    relations = await load_relations(db, kb_id)
    g = nx.DiGraph()
    for rel in relations:
        g.add_node(rel.subject)
        g.add_node(rel.object_entity)
        g.add_edge(
            rel.subject,
            rel.object_entity,
            predicate=rel.predicate,
            chunk_id=rel.chunk_id,
            relation_id=rel.id,
        )
    _cache_set(kb_id, g)
    return g


async def list_entity_names(db: AsyncSession, kb_id: str) -> list[str]:
    relations = await load_relations(db, kb_id)
    names: set[str] = set()
    for rel in relations:
        names.add(rel.subject)
        names.add(rel.object_entity)
    return sorted(names, key=len, reverse=True)


def link_entities_in_query(query: str, entity_names: list[str], *, min_len: int = 2) -> list[str]:
    import re

    q = query.strip()
    terms = set(re.findall(r"[\w\u4e00-\u9fff]{2,}", q))
    stop = {"综合", "知识库", "内容", "说明", "有何", "关联", "两段", "之间", "关系"}
    terms -= stop

    hits: list[str] = []
    seen: set[str] = set()
    for name in entity_names:
        if len(name) < min_len or name in seen:
            continue
        matched = name in q
        if not matched:
            for t in terms:
                if len(t) >= 3 and (t in name or name in t):
                    matched = True
                    break
        if matched:
            hits.append(name)
            seen.add(name)
    return hits


def expand_graph_paths(
    graph: nx.DiGraph,
    seed_entities: list[str],
    *,
    max_hops: int = 2,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    """BFS 扩展，返回 chunk_id 分数与路径列表。"""
    chunk_scores: dict[str, float] = {}
    paths: list[dict[str, Any]] = []
    if not seed_entities or graph.number_of_edges() == 0:
        return chunk_scores, paths

    for seed in seed_entities:
        if seed not in graph:
            continue
        frontier: list[tuple[str, int]] = [(seed, 0)]
        visited: set[str] = {seed}
        while frontier:
            node, depth = frontier.pop(0)
            edges = list(graph.out_edges(node, data=True))
            edges += [(v, u, d) for u, v, d in graph.in_edges(node, data=True)]
            for u, v, data in edges:
                neighbor = v if u == node else u
                cid = data.get("chunk_id")
                pred = data.get("predicate", "关联")
                hop = depth + 1
                if cid:
                    chunk_scores[cid] = max(chunk_scores.get(cid, 0.0), 1.0 / hop)
                    paths.append(
                        {
                            "subject": node,
                            "predicate": pred,
                            "object": neighbor,
                            "chunk_id": cid,
                            "hops": hop,
                        }
                    )
                if neighbor not in visited and hop < max_hops:
                    visited.add(neighbor)
                    frontier.append((neighbor, hop))

    return chunk_scores, paths[:20]


async def graph_snapshot(
    db: AsyncSession,
    kb_id: str,
    *,
    limit_nodes: int = 80,
) -> dict[str, Any]:
    relations = await load_relations(db, kb_id)
    node_set: set[str] = set()
    edges: list[dict[str, Any]] = []
    for rel in relations:
        node_set.add(rel.subject)
        node_set.add(rel.object_entity)
        edges.append(
            {
                "source": rel.subject,
                "target": rel.object_entity,
                "predicate": rel.predicate,
                "chunk_id": rel.chunk_id,
            }
        )
        if len(node_set) >= limit_nodes:
            break

    nodes = [{"id": n, "name": n} for n in sorted(node_set)[:limit_nodes]]
    return {
        "nodes": nodes,
        "edges": edges[: limit_nodes * 2],
        "relation_count": len(relations),
        "node_count": len(node_set),
    }
